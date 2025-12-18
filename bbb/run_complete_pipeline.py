"""
Master Orchestrator - Complete Site Discovery and Testing Pipeline

This script orchestrates the complete workflow:
1. Site Discovery → Finds potential WooCommerce + Braintree sites
2. Gateway Validation → Validates compatibility and generates configs
3. Batch Testing → Tests sites with bbb_final.py
4. Report Generation → Comprehensive analysis and recommendations

Run this to perform end-to-end site discovery and validation.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
import logging

# Import our modules
try:
    from site_discovery import SiteDiscovery
    from gateway_validator import GatewayValidator
    from batch_checker import BatchChecker, HAS_BBB_FINAL
except ImportError as e:
    print(f"[ERROR] Failed to import modules: {e}")
    print("Please ensure all scripts are in the same directory")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MasterOrchestrator:
    """Orchestrates the complete site discovery and testing pipeline"""
    
    def __init__(self):
        self.discovery = SiteDiscovery(max_concurrent=20, timeout=15)
        self.validator = GatewayValidator(timeout=20)
        self.checker = BatchChecker() if HAS_BBB_FINAL else None
        
        self.phase_results = {
            'discovery': None,
            'validation': None,
            'testing': None
        }
    
    async def run_complete_pipeline(self, 
                                    seed_count: int = 200,
                                    validation_enabled: bool = True,
                                    testing_enabled: bool = True,
                                    min_test_score: int = 70):
        """
        Run the complete pipeline.
        
        Args:
            seed_count: Number of seed domains to generate
            validation_enabled: Whether to run validation phase
            testing_enabled: Whether to run testing phase
            min_test_score: Minimum score for testing (0-100)
        """
        print("="  * 90)
        print(" " * 20 + "MASTER ORCHESTRATOR - COMPLETE PIPELINE")
        print("=" * 90)
        print(f"\nPipeline Configuration:")
        print(f"  Seed Count: {seed_count}")
        print(f"  Validation: {'Enabled' if validation_enabled else 'Disabled'}")
        print(f"  Testing: {'Enabled' if testing_enabled and HAS_BBB_FINAL else 'Disabled (bbb_final.py not found)' if testing_enabled else 'Disabled'}")
        print(f"  Min Test Score: {min_test_score}")
        print("=" * 90)
        
        # PHASE 1: Discovery
        await self._phase1_discovery(seed_count)
        
        # PHASE 2: Validation
        if validation_enabled and self.phase_results['discovery']:
            await self._phase2_validation()
        
        # PHASE 3: Testing
        if testing_enabled and HAS_BBB_FINAL and self.phase_results['validation']:
            await self._phase3_testing(min_test_score)
        
        # Generate final report
        self._generate_final_report()
    
    async def _phase1_discovery(self, seed_count: int):
        """Phase 1: Site Discovery"""
        print("\n" + "=" * 90)
        print("PHASE 1: SITE DISCOVERY")
        print("=" * 90)
        
        print(f"\n[1.1] Generating {seed_count} seed domains...")
        seed_domains = self.discovery.generate_seed_domains()[:seed_count]
        print(f"✓ Generated {len(seed_domains)} seed domains")
        
        print(f"\n[1.2] Discovering WooCommerce sites (checking {len(seed_domains)} domains)...")
        print("This may take 5-10 minutes...\n")
        
        start_time = datetime.now()
        discovered_sites = await self.discovery.discover_from_seed_list(seed_domains)
        duration = (datetime.now() - start_time).total_seconds()
        
        print(f"\n✓ Discovery complete in {duration:.1f}s")
        
        # Show statistics
        stats = self.discovery.get_statistics()
        if stats:
            print(f"\nDiscovery Statistics:")
            print(f"  Total WooCommerce sites: {stats['total_discovered']}")
            print(f"  Sites with Braintree: {stats['braintree_sites']} ({stats['braintree_percentage']}%)")
            print(f"  Sites with NMI: {stats['nmi_sites']}")
            print(f"  Average response time: {stats['average_response_time']}s")
        
        # Save results
        self.discovery.save_results('discovered_sites.json')
        self.phase_results['discovery'] = discovered_sites
        
        print(f"\n✓ Phase 1 complete: {len(discovered_sites)} WooCommerce sites discovered")
    
    async def _phase2_validation(self):
        """Phase 2: Gateway Validation"""
        print("\n" + "=" * 90)
        print("PHASE 2: GATEWAY VALIDATION")
        print("=" * 90)
        
        discovered_sites = self.phase_results['discovery']
        if not discovered_sites:
            print("\n[!] No sites to validate")
            return
        
        # Extract domains
        domains = [site.domain for site in discovered_sites]
        
        print(f"\n[2.1] Validating {len(domains)} sites...")
        print("This may take 5-15 minutes...\n")
        
        start_time = datetime.now()
        validated_sites = await self.validator.validate_multiple(domains)
        duration = (datetime.now() - start_time).total_seconds()
        
        print(f"\n✓ Validation complete in {duration:.1f}s")
        
        # Show statistics
        compatible = self.validator.get_compatible_sites(min_score=50)
        high_quality = self.validator.get_compatible_sites(min_score=70)
        
        print(f"\nValidation Statistics:")
        print(f"  Total validated: {len(validated_sites)}")
        print(f"  Compatible (score ≥ 50): {len(compatible)}")
        print(f"  High quality (score ≥ 70): {len(high_quality)}")
        print(f"  Braintree sites: {sum(1 for r in validated_sites if r.has_braintree)}")
        
        # Save results
        self.validator.save_results('validation_report.json')
        self.validator.generate_config_json(min_score=70, filename='high_quality_sites_config.json')
        self.phase_results['validation'] = validated_sites
        
        print(f"\n✓ Phase 2 complete: {len(high_quality)} high-quality sites ready for testing")
    
    async def _phase3_testing(self, min_score: int):
        """Phase 3: Batch Testing"""
        print("\n" + "=" * 90)
        print("PHASE 3: BATCH TESTING")
        print("=" * 90)
        
        validated_sites = self.phase_results['validation']
        if not validated_sites:
            print("\n[!] No sites to test")
            return
        
        # Get high-quality sites
        test_sites = [
            site.domain for site in validated_sites
            if site.overall_score >= min_score and site.has_braintree
        ]
        
        if not test_sites:
            print(f"\n[!] No sites with score ≥ {min_score}")
            return
        
        print(f"\n[3.1] Testing {len(test_sites)} high-quality sites...")
        print("This may take 10-30 minutes depending on site count...\n")
        
        start_time = datetime.now()
        test_results = await self.checker.test_sites(test_sites, max_concurrent=3)
        duration = (datetime.now() - start_time).total_seconds()
        
        print(f"\n✓ Testing complete in {duration:.1f}s")
        
        # Show statistics
        stats = self.checker.get_statistics()
        if stats:
            print(f"\nTesting Statistics:")
            print(f"  Total tested: {stats['total_sites']}")
            print(f"  Successful: {stats['successful']} ({stats['success_rate']}%)")
            print(f"  Partial: {stats['partial']}")
            print(f"  Failed: {stats['failed']}")
            print(f"  Average test duration: {stats['average_test_duration']}s")
        
        # Save results
        self.checker.save_results()
        self.phase_results['testing'] = test_results
        
        print(f"\n✓ Phase 3 complete: {stats.get('successful', 0)} sites fully functional")
    
    def _generate_final_report(self):
        """Generate comprehensive final report"""
        print("\n" + "=" * 90)
        print("FINAL SUMMARY REPORT")
        print("=" * 90)
        
        report_lines = []
        report_lines.append(f"\nPipeline Execution Summary")
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Discovery phase
        if self.phase_results['discovery']:
            discovery_stats = self.discovery.get_statistics()
            report_lines.append("Phase 1: Discovery")
            report_lines.append(f"  Sites found: {discovery_stats.get('total_discovered', 0)}")
            report_lines.append(f"  Braintree sites: {discovery_stats.get('braintree_sites', 0)}")
            report_lines.append("")
        
        # Validation phase
        if self.phase_results['validation']:
            compatible_50 = len(self.validator.get_compatible_sites(50))
            compatible_70 = len(self.validator.get_compatible_sites(70))
            report_lines.append("Phase 2: Validation")
            report_lines.append(f"  Compatible sites (≥50): {compatible_50}")
            report_lines.append(f"  High-quality sites (≥70): {compatible_70}")
            report_lines.append("")
        
        # Testing phase
        if self.phase_results['testing'] and self.checker:
            test_stats = self.checker.get_statistics()
            report_lines.append("Phase 3: Testing")
            report_lines.append(f"  Fully functional: {test_stats.get('successful', 0)}")
            report_lines.append(f"  Partially working: {test_stats.get('partial', 0)}")
            report_lines.append(f"  Success rate: {test_stats.get('success_rate', 0)}%")
            report_lines.append("")
        
        # Output files
        report_lines.append("Generated Files:")
        report_lines.append("  ✓ discovered_sites.json - All discovered WooCommerce sites")
        report_lines.append("  ✓ validation_report.json - Detailed validation results")
        report_lines.append("  ✓ high_quality_sites_config.json - Config for best sites")
        if self.phase_results['testing']:
            report_lines.append("  ✓ batch_test_results.json - Complete test results")
            report_lines.append("  ✓ batch_test_results.csv - Test results (spreadsheet)")
        
        report_lines.append("")
        report_lines.append("=" * 90)
        
        report_text = "\n".join(report_lines)
        print(report_text)
        
        # Save report
        with open('final_report.txt', 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        print("\n✓ Final report saved to final_report.txt")
        print("\n🎉 PIPELINE COMPLETE!")


async def main():
    """Main orchestrator entry point"""
    print("\n" + "=" * 90)
    print(" " * 15 + "ADVANCED SITE DISCOVERY & TESTING SYSTEM")
    print(" " * 25 + "for bbb_final.py")
    print("=" * 90)
    
    print("\nThis tool will:")
    print("  1. Discover WooCommerce sites with Braintree payment gateway")
    print("  2. Validate site compatibility and extract configuration")
    print("  3. Test sites automatically with your payment processor")
    print("  4. Generate comprehensive reports and statistics")
    
    print("\n" + "=" * 90)
    
    # Configuration
    SEED_COUNT = 150  # Number of domains to check
    ENABLE_VALIDATION = True
    ENABLE_TESTING = True  # Set to False to skip actual payment testing
    MIN_TEST_SCORE = 70  # Only test sites with score >= 70
    
    print(f"\nConfiguration:")
    print(f"  Seed domains: {SEED_COUNT}")
    print(f"  Validation: {ENABLE_VALIDATION}")
    print(f"  Testing: {ENABLE_TESTING}")
    print(f"  Min test score: {MIN_TEST_SCORE}")
    
    input("\nPress Enter to start, or Ctrl+C to cancel...")
    
    # Run pipeline
    orchestrator = MasterOrchestrator()
    
    try:
        await orchestrator.run_complete_pipeline(
            seed_count=SEED_COUNT,
            validation_enabled=ENABLE_VALIDATION,
            testing_enabled=ENABLE_TESTING,
            min_test_score=MIN_TEST_SCORE
        )
    except KeyboardInterrupt:
        print("\n\n[!] Pipeline interrupted by user")
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        print(f"\n[ERROR] Pipeline failed: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Cancelled")
