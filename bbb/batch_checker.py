"""
Batch Checker - Automated Site Testing with bbb_final.py Integration

This tool performs automated batch testing of discovered sites using the enhanced
bbb_final.py processor. It provides comprehensive reporting and analytics.

Features:
- Batch processing with progress tracking
- Integration with circuit breaker
- Detailed per-site results
- Aggregated statistics and analytics
- CSV/JSON export
- Failure analysis
"""

import asyncio
import json
import csv
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from bbb_final import (
        test_single_site,
        CardDetails,
        get_config_manager,
        get_circuit_breaker
    )
    HAS_BBB_FINAL = True
except ImportError:
    HAS_BBB_FINAL = False
    print("[WARNING] bbb_final.py not found - running in analysis-only mode")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class BatchTestResult:
    """Result from batch testing"""
    domain: str
    tested_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Test results
    step1_registration: str = "PENDING"
    step2_login: str = "PENDING"
    step3_billing: str = "PENDING"
    step4_payment_method: str = "PENDING"
    overall_status: str = "PENDING"
    
    # Timing
    test_duration: float = 0.0
    
    # Errors
    error_message: str = ""
    error_type: str = ""
    
    # Circuit breaker
    circuit_breaker_state: str = "closed"
    
    # Card info
    card_used: str = ""
    
    def to_dict(self):
        return asdict(self)
    
    def is_success(self) -> bool:
        return self.overall_status == "SUCCESS"
    
    def is_partial(self) -> bool:
        return self.step1_registration == "PASS" or self.step2_login == "PASS"


class BatchChecker:
    """Batch testing orchestrator"""
    
    def __init__(self, test_card: str = "5403850087142766|11|2028|427"):
        """
        Initialize batch checker.
        
        Args:
            test_card: Test card in format number|month|year|cvv
        """
        self.test_card = test_card
        self.results: List[BatchTestResult] = []
        self.start_time = None
        self.end_time = None
        
        if HAS_BBB_FINAL:
            self.config_mgr = get_config_manager()
            self.circuit_breaker = get_circuit_breaker()
        else:
            self.config_mgr = None
            self.circuit_breaker = None
    
    async def test_sites(self, domains: List[str], max_concurrent: int = 3) -> List[BatchTestResult]:
        """
        Test multiple sites in batch.
        
        Args:
            domains: List of domains to test
            max_concurrent: Maximum concurrent tests (to avoid overwhelming sites)
            
        Returns:
            List of test results
        """
        if not HAS_BBB_FINAL:
            logger.error("Cannot test sites - bbb_final.py not available")
            return []
        
        logger.info(f"Starting batch test of {len(domains)} sites")
        self.start_time = datetime.now()
        
        # Parse test card
        try:
            parts = self.test_card.split("|")
            card = CardDetails(
                number=parts[0],
                expiry_month=parts[1],
                expiry_year=parts[2],
                cvv=parts[3]
            )
        except Exception as e:
            logger.error(f"Invalid test card format: {e}")
            return []
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def test_with_semaphore(domain: str, index: int):
            async with semaphore:
                return await self._test_single_site_wrapper(domain, card, index, len(domains))
        
        # Run tests
        tasks = [test_with_semaphore(domain, i) for i, domain in enumerate(domains, 1)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        self.results = [r for r in results if isinstance(r, BatchTestResult)]
        
        self.end_time = datetime.now()
        logger.info(f"Batch test complete: {len(self.results)} sites tested")
        
        return self.results
    
    async def _test_single_site_wrapper(self, domain: str, card: CardDetails,
                                       index: int, total: int) -> BatchTestResult:
        """Wrapper for testing a single site with error handling"""
        result = BatchTestResult(
            domain=domain,
            card_used=card.masked_number()
        )
        
        print(f"\n[{index}/{total}] Testing {domain}...")
        start = datetime.now()
        
        try:
            # Check circuit breaker
            if self.circuit_breaker and not self.circuit_breaker.can_attempt(domain):
                result.circuit_breaker_state = self.circuit_breaker.get_state(domain)
                result.overall_status = "SKIP"
                result.error_message = "Circuit breaker open"
                print(f"  [SKIP] Circuit breaker {result.circuit_breaker_state}")
                return result
            
            # Run actual test
            test_result = await test_single_site(domain, card)
            
            # Map results
            result.step1_registration = test_result.get('step1_registration', 'ERROR')
            result.step2_login = test_result.get('step2_login', 'ERROR')
            result.step3_billing = test_result.get('step3_billing', 'ERROR')
            result.step4_payment_method = test_result.get('step4_payment_method', 'ERROR')
            result.overall_status = test_result.get('overall', 'ERROR')
            result.error_message = test_result.get('error', '')
            
            # Update circuit breaker
            if self.circuit_breaker:
                if result.overall_status == 'SUCCESS':
                    self.circuit_breaker.record_success(domain)
                elif result.overall_status in ['FAIL', 'ERROR']:
                    self.circuit_breaker.record_failure(domain)
                result.circuit_breaker_state = self.circuit_breaker.get_state(domain)
            
            print(f"  [{result.overall_status}] {domain}")
            
        except Exception as e:
            result.overall_status = "ERROR"
            result.error_type = type(e).__name__
            result.error_message = str(e)[:200]
            logger.error(f"Error testing {domain}: {e}")
            print(f"  [ERROR] {type(e).__name__}")
        
        finally:
            result.test_duration = (datetime.now() - start).total_seconds()
        
        return result
    
    def get_statistics(self) -> Dict:
        """Generate comprehensive statistics"""
        if not self.results:
            return {}
        
        total = len(self.results)
        successful = sum(1 for r in self.results if r.is_success())
        partial = sum(1 for r in self.results if r.is_partial() and not r.is_success())
        failed = total - successful - partial
        skipped = sum(1 for r in self.results if r.overall_status == "SKIP")
        
        # Calculate average test duration
        durations = [r.test_duration for r in self.results if r.test_duration > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Error analysis
        error_types = {}
        for r in self.results:
            if r.error_type:
                error_types[r.error_type] = error_types.get(r.error_type, 0) + 1
        
        # Step analysis
        step_stats = {
            'registration_pass': sum(1 for r in self.results if r.step1_registration == 'PASS'),
            'login_pass': sum(1 for r in self.results if r.step2_login == 'PASS'),
            'billing_pass': sum(1 for r in self.results if r.step3_billing == 'PASS'),
            'payment_pass': sum(1 for r in self.results if r.step4_payment_method == 'PASS'),
        }
        
        # Total test time
        total_time = 0
        if self.start_time and self.end_time:
            total_time = (self.end_time - self.start_time).total_seconds()
        
        return {
            'total_sites': total,
            'successful': successful,
            'partial': partial,
            'failed': failed,
            'skipped': skipped,
            'success_rate': round(successful / total * 100, 1) if total > 0 else 0,
            'average_test_duration': round(avg_duration, 2),
            'total_test_time': round(total_time, 2),
            'step_statistics': step_stats,
            'error_types': error_types
        }
    
    def save_results(self, json_file: str = "batch_test_results.json",
                    csv_file: str = "batch_test_results.csv"):
        """Save results to JSON and CSV"""
        # JSON
        data = {
            'test_started': self.start_time.isoformat() if self.start_time else None,
            'test_completed': self.end_time.isoformat() if self.end_time else None,
            'statistics': self.get_statistics(),
            'results': [r.to_dict() for r in self.results]
        }
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Saved JSON results to {json_file}")
        
        # CSV
        if self.results:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.results[0].to_dict().keys())
                writer.writeheader()
                for result in self.results:
                    writer.writerow(result.to_dict())
            logger.info(f"✓ Saved CSV results to {csv_file}")
    
    def generate_report(self) -> str:
        """Generate human-readable report"""
        stats = self.get_statistics()
        
        report = []
        report.append("=" * 80)
        report.append("BATCH TEST REPORT")
        report.append("=" * 80)
        report.append(f"\nTest Period: {self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else 'N/A'}")
        report.append(f"Total Duration: {stats.get('total_test_time', 0):.1f} seconds")
        report.append(f"\nSummary:")
        report.append(f"  Total Sites: {stats.get('total_sites', 0)}")
        report.append(f"  Successful: {stats.get('successful', 0)} ({stats.get('success_rate', 0)}%)")
        report.append(f"  Partial: {stats.get('partial', 0)}")
        report.append(f"  Failed: {stats.get('failed', 0)}")
        report.append(f"  Skipped: {stats.get('skipped', 0)}")
        report.append(f"\nPerformance:")
        report.append(f"  Average Test Duration: {stats.get('average_test_duration', 0):.2f}s")
        
        # Step statistics
        step_stats = stats.get('step_statistics', {})
        if step_stats:
            report.append(f"\nStep-by-Step Success:")
            report.append(f"  Registration: {step_stats.get('registration_pass', 0)}")
            report.append(f"  Login: {step_stats.get('login_pass', 0)}")
            report.append(f"  Billing: {step_stats.get('billing_pass', 0)}")
            report.append(f"  Payment: {step_stats.get('payment_pass', 0)}")
        
        # Error analysis
        error_types = stats.get('error_types', {})
        if error_types:
            report.append(f"\nError Types:")
            for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
                report.append(f"  {error_type}: {count}")
        
        # Top successful sites
        successful = [r for r in self.results if r.is_success()]
        if successful:
            report.append(f"\nSuccessful Sites ({len(successful)}):")
            for r in successful[:10]:
                report.append(f"  ✓ {r.domain} ({r.test_duration:.1f}s)")
        
        # Failed sites with reasons
        failed = [r for r in self.results if not r.is_success() and r.overall_status != 'SKIP']
        if failed:
            report.append(f"\nFailed Sites ({len(failed)}):")
            for r in failed[:10]:
                report.append(f"  ✗ {r.domain}: {r.error_message[:60]}")
        
        report.append("=" * 80)
        
        return "\n".join(report)


async def main():
    """Main batch testing function"""
    print("=" * 80)
    print("BATCH CHECKER - AUTOMATED SITE TESTING")
    print("=" * 80)
    
    if not HAS_BBB_FINAL:
        print("\n[ERROR] bbb_final.py not found in current directory")
        print("Please ensure bbb_final.py is in the same directory")
        return
    
    # Load sites from validation report
    domains = []
    try:
        with open('validation_report.json', 'r') as f:
            data = json.load(f)
            # Get sites with score >= 70
            results = data.get('results', [])
            domains = [
                r['domain'] for r in results 
                if r.get('overall_score', 0) >= 70 and r.get('has_braintree', False)
            ]
    except FileNotFoundError:
        print("\n[WARNING] validation_report.json not found")
        print("Using discovered_sites.json instead...")
        
        try:
            with open('discovered_sites.json', 'r') as f:
                data = json.load(f)
                domains = [
                    s['domain'] for s in data.get('sites', [])
                    if s.get('has_braintree', False)
                ]
        except FileNotFoundError:
            print("\n[ERROR] No site data found")
            print("Please run site_discovery.py and gateway_validator.py first")
            return
    
    if not domains:
        print("\n[ERROR] No compatible sites found")
        return
    
    print(f"\n[1] Found {len(domains)} compatible sites")
    print(f"[2] Starting batch test (max 3 concurrent)...")
    print("\nThis may take a while...\n")
    
    # Create checker and run tests
    checker = BatchChecker()
    results = await checker.test_sites(domains, max_concurrent=3)
    
    # Display report
    print("\n")
    print(checker.generate_report())
    
    # Save results
    print(f"\n{'='*80}")
    checker.save_results()
    print("✓ Complete! Check batch_test_results.json and batch_test_results.csv")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[!] Batch test interrupted by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
