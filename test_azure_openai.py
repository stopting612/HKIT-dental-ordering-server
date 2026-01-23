"""
Azure OpenAI Configuration Diagnostic Tool

This script helps diagnose 404 errors from Azure OpenAI
"""

from dotenv import load_dotenv
import os
from openai import AzureOpenAI

load_dotenv()

def check_azure_config():
    """Check Azure OpenAI configuration"""
    print("="*60)
    print("Azure OpenAI Configuration Check")
    print("="*60)
    
    # Read environment variables
    endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    api_key = os.getenv('AZURE_OPENAI_KEY')
    deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT')
    api_version = os.getenv('AZURE_OPENAI_API_VERSION')
    
    issues = []
    
    # Check endpoint format
    print("\n1. Endpoint Check:")
    print(f"   Value: {endpoint}")
    if not endpoint:
        issues.append("❌ AZURE_OPENAI_ENDPOINT is not set")
    elif not endpoint.endswith('/'):
        issues.append("⚠️  Endpoint should end with '/'")
        print(f"   Suggested: {endpoint}/")
    elif 'cognitiveservices.azure.com' not in endpoint:
        issues.append("⚠️  Endpoint should use 'cognitiveservices.azure.com' domain")
        print("   Example: https://YOUR-RESOURCE.cognitiveservices.azure.com/")
    else:
        print("   ✅ Format looks correct")
    
    # Check API key
    print("\n2. API Key Check:")
    if not api_key:
        issues.append("❌ AZURE_OPENAI_KEY is not set")
    elif len(api_key) < 20:
        issues.append("⚠️  API key seems too short (might be invalid)")
    else:
        print(f"   ✅ Key present (length: {len(api_key)})")
    
    # Check deployment name
    print("\n3. Deployment Name Check:")
    print(f"   Value: {deployment}")
    if not deployment:
        issues.append("❌ AZURE_OPENAI_DEPLOYMENT is not set")
    else:
        print("   ⚠️  Verify this matches your Azure Portal deployment name exactly")
    
    # Check API version
    print("\n4. API Version Check:")
    print(f"   Value: {api_version}")
    if not api_version:
        issues.append("❌ AZURE_OPENAI_API_VERSION is not set")
    elif api_version != "2024-12-01-preview":
        issues.append(f"⚠️  For GPT-5.2, recommended version is '2024-12-01-preview'")
        print(f"   Current: {api_version}")
        print(f"   Recommended: 2024-12-01-preview")
    else:
        print("   ✅ Correct for GPT-5.2")
    
    # Summary
    print("\n" + "="*60)
    if issues:
        print("Issues Found:")
        for issue in issues:
            print(f"  {issue}")
        print("\n💡 Fix these issues in your .env file")
    else:
        print("✅ All configuration looks good!")
        print("\n🔍 Testing connection...")
        test_connection(endpoint, api_key, deployment, api_version)
    
    print("="*60)


def test_connection(endpoint, api_key, deployment, api_version):
    """Test actual connection to Azure OpenAI"""
    try:
        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version
        )
        
        print("\nSending test request...")
        response = client.chat.completions.create(
            model=deployment,
            messages=[{"role": "user", "content": "Hello"}],
            max_completion_tokens=10  # GPT-5.2 uses max_completion_tokens, not max_tokens
        )
        
        print("✅ Connection successful!")
        print(f"   Response: {response.choices[0].message.content}")
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ Connection failed:")
        print(f"   {error_msg}")
        
        if '404' in error_msg:
            print("\n💡 404 Error Solutions:")
            print("   1. Verify deployment name in Azure Portal")
            print("   2. Check endpoint URL format")
            print("   3. Ensure API version is correct")
            print("\n   Example correct format:")
            print("   AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.cognitiveservices.azure.com/")
            print("   AZURE_OPENAI_DEPLOYMENT=gpt-5.2-chat")
            print("   AZURE_OPENAI_API_VERSION=2024-12-01-preview")
        elif '401' in error_msg:
            print("\n💡 401 Error: Invalid API key")
            print("   Get key from Azure Portal > Your OpenAI Resource > Keys and Endpoint")


if __name__ == "__main__":
    check_azure_config()
