from datetime import date
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine, Base
from app.core.security import hash_password
from app.models.user import User
from app.models.partner import Partner
from app.models.source import Source
from app.models.rate_card import RateCard


def seed_master_data(db: Session) -> None:
    print("Seeding database master records...")

    # 1. Seed Demo Users
    demo_users = [
        {
            "email": "finance_exec@company-a.com",
            "password": "Password123!",
            "role": "finance_exec"
        },
        {
            "email": "cofounder@company-a.com",
            "password": "Password123!",
            "role": "cofounder"
        }
    ]

    for u in demo_users:
        existing = db.query(User).filter(User.email == u["email"]).first()
        if not existing:
            user = User(
                email=u["email"],
                password_hash=hash_password(u["password"]),
                role=u["role"]
            )
            db.add(user)
            print(f"Created demo user: {u['email']} ({u['role']})")

    # 2. Seed Demo Partners
    demo_partners = [
        {"id": "shopify", "name": "Company A Website (Shopify)", "partner_type": "d2c_storefront", "channel": "d2c"},
        {"id": "amazon", "name": "Amazon India", "partner_type": "marketplace", "channel": "marketplace"},
        {"id": "flipkart", "name": "Flipkart", "partner_type": "marketplace", "channel": "marketplace"},
        {"id": "myntra", "name": "Myntra", "partner_type": "marketplace", "channel": "marketplace"},
        {"id": "blinkit", "name": "Blinkit Quick Commerce", "partner_type": "quick_commerce", "channel": "quick_commerce"},
        {"id": "zepto", "name": "Zepto Quick Commerce", "partner_type": "quick_commerce", "channel": "quick_commerce"},
        {"id": "delhivery", "name": "Delhivery Logistics", "partner_type": "courier_aggregator", "channel": "courier"},
        {"id": "bluedart", "name": "Blue Dart Express", "partner_type": "courier_aggregator", "channel": "courier"},
        {"id": "blr_warehouse", "name": "Bengaluru Central Warehouse", "partner_type": "warehouse", "channel": "warehouse"},
    ]

    for p in demo_partners:
        existing = db.query(Partner).filter(Partner.id == p["id"]).first()
        if not existing:
            partner = Partner(**p)
            db.add(partner)
            print(f"Created partner: {p['name']} ({p['id']})")

    db.flush()

    # 3. Seed Sources
    demo_sources = [
        {"partner_id": "shopify", "source_type": "orders"},
        {"partner_id": "shopify", "source_type": "settlement"},
        {"partner_id": "delhivery", "source_type": "cod"},
        {"partner_id": "delhivery", "source_type": "freight"},
        {"partner_id": "bluedart", "source_type": "cod"},
        {"partner_id": "bluedart", "source_type": "freight"},
        {"partner_id": "amazon", "source_type": "settlement"},
        {"partner_id": "flipkart", "source_type": "settlement"},
        {"partner_id": "blr_warehouse", "source_type": "receipts"},
    ]

    for s in demo_sources:
        existing = db.query(Source).filter(
            Source.partner_id == s["partner_id"],
            Source.source_type == s["source_type"]
        ).first()
        if not existing:
            source = Source(**s)
            db.add(source)

    db.flush()

    # 4. Seed Calibrated Rate Cards
    demo_rate_cards = [
        # Sample 1 Calibrated Rate Card: Website COD (ORD-W-204118 -> Order Value ₹1,499, Expected ₹1,409)
        {
            "partner_id": "shopify",
            "channel": "d2c",
            "rule_type": "website_cod",
            "params_json": {
                "commission_pct": 0.0,
                "fixed_fee": 0.0,
                "forward_shipping_fee": 60.00,
                "cod_handling_fee": 30.00,
                "cod_due_days": 7,
                "description": "D2C Website COD: Flat ₹60 shipping + ₹30 COD collection"
            },
            "valid_from": date(2026, 1, 1),
            "valid_until": None,
            "is_active": True
        },
        # Sample 2 Calibrated Rate Card: Marketplace 1 (ORD-M-88120 -> Order Value ₹1,199, Expected ₹899)
        {
            "partner_id": "amazon",
            "channel": "marketplace",
            "rule_type": "marketplace_standard",
            "params_json": {
                "commission_pct": 15.0,  # 15% of 1199 = 179.85
                "fixed_fee": 30.15,      # 179.85 + 30.15 = 210.00
                "forward_shipping_fee": 90.00, # Total deductions = 300.00 -> Net 899.00
                "settlement_due_days": 10,
                "description": "Amazon standard textile tariff: 15% comm + ₹30.15 closing + ₹90 logistics"
            },
            "valid_from": date(2026, 1, 1),
            "valid_until": None,
            "is_active": True
        },
        # Sample 3 Calibrated Rate Card: D2C Prepaid Return (ORD-W-204377 -> Expected Net -₹96)
        {
            "partner_id": "shopify",
            "channel": "d2c",
            "rule_type": "website_prepaid",
            "params_json": {
                "commission_pct": 0.0,
                "fixed_fee": 0.0,
                "forward_shipping_fee": 60.00,
                "reverse_shipping_fee": 36.00, # -60 forward - 36 reverse = -96 net
                "settlement_due_days": 3,
                "return_receipt_grace_days": 7,
                "description": "D2C Prepaid Home Textiles: ₹60 fwd, ₹36 rev"
            },
            "valid_from": date(2026, 1, 1),
            "valid_until": None,
            "is_active": True
        },
        # Courier Aggregator Rate Card
        {
            "partner_id": "delhivery",
            "channel": "courier",
            "rule_type": "courier_standard",
            "params_json": {
                "base_weight_kg": 0.5,
                "base_rate": 50.00,
                "additional_weight_step_kg": 0.5,
                "additional_weight_rate": 25.00,
                "rto_charge_factor": 0.6, # Reverse rate is 60% of forward
                "description": "Delhivery standard surface logistics rate card"
            },
            "valid_from": date(2026, 1, 1),
            "valid_until": None,
            "is_active": True
        }
    ]

    for rc in demo_rate_cards:
        existing = db.query(RateCard).filter(
            RateCard.partner_id == rc["partner_id"],
            RateCard.channel == rc["channel"],
            RateCard.rule_type == rc["rule_type"],
            RateCard.valid_from == rc["valid_from"]
        ).first()
        if not existing:
            card = RateCard(**rc)
            db.add(card)
            print(f"Created rate card: {rc['partner_id']} ({rc['rule_type']})")

    db.commit()
    print("Database seeding completed successfully.")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_master_data(db)
    finally:
        db.close()
