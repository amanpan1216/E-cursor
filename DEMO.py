"""
DEMO.py - Quick Demo of AUTH and CHARGE
Shows how to use both checkers programmatically.
"""

import asyncio
from AUTH import auth_check, Card as AuthCard, Status as AuthStatus
from CHARGE import charge_check, Card as ChargeCard, Status as ChargeStatus

async def demo():
    """Demo both AUTH and CHARGE checkers."""
    
    print("=" * 80)
    print("BRAINTREE CHECKER SUITE - DEMO")
    print("=" * 80)
    print()
    
    # Test card
    card_data = ('5403850087142766', '11', '2028', '427')
    
    # Demo site (change to your test site)
    site = 'djcity.com.au'
    
    print(f"Testing site: {site}")
    print(f"Card: {card_data[0][:6]}******{card_data[0][-4:]}")
    print()
    
    # ========================================================================
    # TEST 1: AUTH - Add Payment Method
    # ========================================================================
    print("─" * 80)
    print("TEST 1: AUTH - Add Payment Method")
    print("─" * 80)
    
    auth_card = AuthCard(*card_data)
    auth_result = await auth_check(site, auth_card)
    
    print(f"Status: {auth_result.status.value}")
    print(f"Message: {auth_result.message}")
    print(f"Method: {auth_result.method}")
    
    if auth_result.status == AuthStatus.APPROVED:
        print("✅ AUTH PASSED - Card approved for saving!")
    elif auth_result.status == AuthStatus.DECLINED:
        print("❌ AUTH DECLINED - Card rejected")
    else:
        print("⚠️ AUTH ERROR - Check configuration")
    
    print()
    
    # ========================================================================
    # TEST 2: CHARGE - Checkout Based
    # ========================================================================
    print("─" * 80)
    print("TEST 2: CHARGE - Checkout & Transaction")
    print("─" * 80)
    
    charge_card = ChargeCard(*card_data)
    charge_result = await charge_check(site, charge_card)
    
    print(f"Status: {charge_result.status.value}")
    print(f"Message: {charge_result.message}")
    if charge_result.product:
        print(f"Product: {charge_result.product}")
    if charge_result.amount:
        print(f"Amount: ${charge_result.amount}")
    print(f"Method: {charge_result.method}")
    
    if charge_result.status == ChargeStatus.CHARGED:
        print(f"✅ CHARGE SUCCESS - Card charged ${charge_result.amount}!")
    elif charge_result.status == ChargeStatus.DECLINED:
        print("❌ CHARGE DECLINED - Transaction rejected")
    else:
        print("⚠️ CHARGE ERROR - Check configuration")
    
    print()
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print()
    print("📊 Results:")
    print(f"  AUTH:   {auth_result.status.value}")
    print(f"  CHARGE: {charge_result.status.value}")
    print()
    print("📝 What's Next:")
    print("  1. Edit SITES list in AUTH.py or CHARGE.py")
    print("  2. Change CARD details for your test card")
    print("  3. Run: python3 AUTH.py (for quick checks)")
    print("  4. Run: python3 CHARGE.py (for complete tests)")
    print("  5. Run: python3 bbb.py (for debugging)")
    print()
    print("📚 Documentation:")
    print("  - README.md: Complete guide")
    print("  - SUMMARY.md: Feature overview")
    print()
    print("🚀 All systems ready!")

if __name__ == "__main__":
    asyncio.run(demo())
