from sqlalchemy import text
from app.core.database import engine, Base
from app.models import (
    User,
    LoginAttempt,
    Partner,
    Source,
    RateCard,
    CourierTrackingRule,
    CourierRuleActivation,
    CourierRuleActivationHistory,
    OrderEvent,
    EventLineageLock
)


TRIGGER_DDL = """
-- 1. Enable btree_gist extension for half-open date range exclusion constraints
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 2. Trigger: Strictly Append-Only order_events (Blocks UPDATE and DELETE)
CREATE OR REPLACE FUNCTION trg_enforce_append_only()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Table % is strictly append-only. UPDATE and DELETE operations are forbidden.', TG_TABLE_NAME
    USING ERRCODE = 'integrity_constraint_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_order_events_immutable ON order_events;
CREATE TRIGGER trg_order_events_immutable
BEFORE UPDATE OR DELETE ON order_events
FOR EACH ROW EXECUTE FUNCTION trg_enforce_append_only();

-- 3. Trigger: Courier Tracking Rule Immutability once approved
CREATE OR REPLACE FUNCTION trg_enforce_tracking_rule_immutability()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.approved_at IS NOT NULL THEN
        RAISE EXCEPTION 'Approved courier tracking mapping version % is immutable. Create version % instead.',
            OLD.version, (OLD.version + 1);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_courier_rules_immutable ON courier_tracking_rules;
CREATE TRIGGER trg_courier_rules_immutable
BEFORE UPDATE OR DELETE ON courier_tracking_rules
FOR EACH ROW EXECUTE FUNCTION trg_enforce_tracking_rule_immutability();

-- 4. Trigger: Phase A (BEFORE INSERT) on order_events - Lineage Locking & Integrity Validation
CREATE OR REPLACE FUNCTION trg_order_events_before_insert()
RETURNS TRIGGER 
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    parent_event RECORD;
    target_leaf RECORD;
    existing_reversals_total NUMERIC(12,2);
    lock_acquired UUID;
    curr_parent UUID;
    depth INT := 0;
BEGIN
    -- Scenario A: Original Event (Root Inception)
    IF NEW.supersedes_event_id IS NULL AND NEW.reverses_event_id IS NULL THEN
        NEW.lineage_root_id := NEW.id;
        RETURN NEW;
    END IF;

    -- Scenario B: Child Event (Correction or Reversal)
    IF NEW.supersedes_event_id IS NOT NULL AND NEW.reverses_event_id IS NOT NULL THEN
        RAISE EXCEPTION 'Ambiguous event %: Cannot be both a correction and a reversal', NEW.id;
    END IF;

    -- Fetch parent to establish lineage root
    IF NEW.supersedes_event_id IS NOT NULL THEN
        SELECT * INTO parent_event FROM order_events WHERE id = NEW.supersedes_event_id;
    ELSE
        SELECT * INTO parent_event FROM order_events WHERE id = NEW.reverses_event_id;
    END IF;

    IF parent_event IS NULL THEN
        RAISE EXCEPTION 'Parent event does not exist for child event %', NEW.id;
    END IF;

    -- Enforce identical business context (cross-order / cross-partner blocked)
    IF parent_event.external_order_id <> NEW.external_order_id OR parent_event.source_partner_id <> NEW.source_partner_id THEN
        RAISE EXCEPTION 'Cross-order or cross-partner child event rejected for parent %', parent_event.id;
    END IF;

    NEW.lineage_root_id := parent_event.lineage_root_id;

    -- ACQUIRE EXCLUSIVE LOCK ON LINEAGE ROOT
    SELECT lineage_root_id INTO lock_acquired 
    FROM event_lineage_locks 
    WHERE lineage_root_id = NEW.lineage_root_id 
    FOR UPDATE;

    IF lock_acquired IS NULL THEN
        RAISE EXCEPTION 'Lineage lock for root % does not exist. Child insertion rejected.', NEW.lineage_root_id
        USING ERRCODE = 'data_exception';
    END IF;

    -- Cycle detection up to depth 50 for supersession chains
    IF NEW.supersedes_event_id IS NOT NULL THEN
        curr_parent := NEW.supersedes_event_id;
        WHILE curr_parent IS NOT NULL LOOP
            depth := depth + 1;
            IF curr_parent = NEW.id THEN
                RAISE EXCEPTION 'Circular supersession detected involving event %', NEW.id;
            END IF;
            IF depth > 50 THEN
                RAISE EXCEPTION 'Supersession chain exceeded maximum allowable depth (50) for event %', NEW.id;
            END IF;
            SELECT supersedes_event_id INTO curr_parent FROM order_events WHERE id = curr_parent;
        END LOOP;
    END IF;

    -- Reversal Validation under Exclusive Lock
    IF NEW.reverses_event_id IS NOT NULL THEN
        IF parent_event.reverses_event_id IS NOT NULL OR parent_event.event_type = 'settlement_reversal' THEN
            RAISE EXCEPTION 'Cannot reverse a reversal (Event %)', NEW.reverses_event_id;
        END IF;

        IF SIGN(NEW.amount) = SIGN(parent_event.amount) OR NEW.amount = 0 THEN
            RAISE EXCEPTION 'Reversal must have opposite sign of parent event';
        END IF;

        -- Identify active correction leaf of this lineage
        SELECT * INTO target_leaf FROM order_events 
        WHERE lineage_root_id = NEW.lineage_root_id 
          AND NOT EXISTS (SELECT 1 FROM order_events s WHERE s.supersedes_event_id = order_events.id);

        SELECT COALESCE(SUM(ABS(amount)), 0.00) INTO existing_reversals_total
        FROM order_events
        WHERE lineage_root_id = NEW.lineage_root_id 
          AND reverses_event_id IS NOT NULL;

        IF (existing_reversals_total + ABS(NEW.amount)) > ABS(target_leaf.amount) THEN
            RAISE EXCEPTION 'Cumulative reversals (₹%) exceed active lineage amount (₹%)',
                (existing_reversals_total + ABS(NEW.amount)), ABS(target_leaf.amount);
        END IF;
    END IF;

    -- Correction Validation under Exclusive Lock
    IF NEW.supersedes_event_id IS NOT NULL THEN
        SELECT COALESCE(SUM(ABS(amount)), 0.00) INTO existing_reversals_total
        FROM order_events
        WHERE lineage_root_id = NEW.lineage_root_id 
          AND reverses_event_id IS NOT NULL;

        IF ABS(NEW.amount) < existing_reversals_total THEN
            RAISE EXCEPTION 'Amended amount (₹%) cannot be less than active reversals (₹%)',
                ABS(NEW.amount), existing_reversals_total;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 5. Trigger: Phase B (AFTER INSERT) on order_events - Creates Root Lock Record
CREATE OR REPLACE FUNCTION trg_order_events_after_insert()
RETURNS TRIGGER 
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF NEW.supersedes_event_id IS NULL AND NEW.reverses_event_id IS NULL THEN
        INSERT INTO event_lineage_locks (lineage_root_id, locked_at) 
        VALUES (NEW.id, NOW())
        ON CONFLICT (lineage_root_id) DO NOTHING;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_order_events_before_ins ON order_events;
CREATE TRIGGER trg_order_events_before_ins
BEFORE INSERT ON order_events
FOR EACH ROW EXECUTE FUNCTION trg_order_events_before_insert();

DROP TRIGGER IF EXISTS trg_order_events_after_ins ON order_events;
CREATE TRIGGER trg_order_events_after_ins
AFTER INSERT ON order_events
FOR EACH ROW EXECUTE FUNCTION trg_order_events_after_insert();

-- 6. View: Active Approved Courier Tracking Rules
CREATE OR REPLACE VIEW active_courier_tracking_rules AS
SELECT r.*
FROM courier_tracking_rules r
JOIN courier_rule_activations a ON r.id = a.active_rule_id
WHERE r.approved_at IS NOT NULL;
"""


def init_database():
    print("Initializing database tables and constraints...")
    # First create btree_gist extension before creating tables with ExcludeConstraint
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist;"))

    Base.metadata.create_all(bind=engine)
    print("Tables created.")

    print("Applying database triggers and views...")
    with engine.begin() as conn:
        conn.execute(text(TRIGGER_DDL))
    print("Triggers and views successfully installed.")


if __name__ == "__main__":
    init_database()
