from platforms_agent import run_growth_system

def main():
    """
    Main entry point for the Growth Agentic System
    """
    # Test the system
    test_company = "A sustainable fashion startup that creates eco-friendly clothing from recycled materials."
    test_audience = "Environmentally conscious millennials and Gen Z (ages 22-35) who value sustainability."
    
    print("🧪 Testing Growth Agentic System...")
    result = run_growth_system(test_company, test_audience)
    
    print("\n" + "="*60)
    print("📋 GROWTH STRATEGY RESULTS")
    print("="*60)
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        if "raw_response" in result:
            print(f"Raw response: {result['raw_response']}")
    else:
        print("\n📱 SELECTED PLATFORMS:")
        for platform in result['selected_platforms']:
            print(f"  {platform['priority']}. {platform['platform']}")
            print(f"     Rationale: {platform['rationale']}\n")
        
        print("\n🎯 CONTENT STRATEGIES:")
        for platform, strategy in result['content_strategies'].items():
            print(f"\n--- {platform.upper()} STRATEGY ---")
            print(f"Priority: {strategy['priority']}")
            print(f"Content Strategy:\n{strategy['content_strategy']}")
            print("-" * 50)

if __name__ == "__main__":
    main()



