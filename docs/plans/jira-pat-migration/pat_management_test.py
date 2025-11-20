#!/usr/bin/env python3
"""
Confluence/Jira Personal Access Token (PAT) Management Test Script

This script demonstrates the full lifecycle of PAT management:
1. Authenticate with existing PAT to validate it works
2. Create a new PAT valid for 45 days
3. Authenticate with the new PAT
4. Optionally revoke the old PAT (can auto-identify current PAT)

Requirements:
- requests library

Usage:
    python pat_management_test.py --base-url https://your-instance.com --existing-pat YOUR_EXISTING_PAT
    
    # Recommended: Use prefix-based naming for easy management
    python pat_management_test.py --base-url https://your-instance.com --existing-pat YOUR_EXISTING_PAT --pat-name-prefix "my-app" --revoke-prefix-pats
    
    # To revoke a specific PAT:
    python pat_management_test.py --base-url https://your-instance.com --existing-pat YOUR_EXISTING_PAT --revoke-pat-id 123
    # or by name:
    python pat_management_test.py --base-url https://your-instance.com --existing-pat YOUR_EXISTING_PAT --revoke-pat-name "old-token"
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import requests


class PATManager:
    """Manages Personal Access Tokens via REST API"""
    
    def __init__(self, base_url: str, username: str = None):
        """
        Initialize the PAT manager
        
        Args:
            base_url: Base URL of the instance (e.g., https://url.company.com)
            username: Username for PAT creation (if different from token owner)
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        # Disable SSL warnings if needed (not recommended for production)
        requests.urllib3.disable_warnings(requests.urllib3.exceptions.InsecureRequestWarning)
    
    def _make_request(self, method: str, endpoint: str, auth_token: str, 
                     data: Dict = None, params: Dict = None) -> Tuple[bool, Dict]:
        """
        Make authenticated HTTP request to the API
        
        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint path
            auth_token: Bearer token for authentication
            data: Request body data
            params: Query parameters
            
        Returns:
            Tuple of (success: bool, response_data: dict)
        """
        url = f"{self.base_url}{endpoint}"
        headers = {'Authorization': f'Bearer {auth_token}'}
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=data if data else None,
                params=params,
                timeout=30,
                verify=False  # Set to True in production with proper SSL
            )
            
            # Handle empty responses (like 204 No Content)
            if response.status_code == 204 or not response.text.strip():
                response_data = {'message': 'Success (No Content)'}
            elif response.headers.get('content-type', '').startswith('application/json'):
                try:
                    response_data = response.json()
                except ValueError as e:
                    # Handle cases where content-type says JSON but content isn't valid JSON
                    response_data = {'message': response.text, 'parse_error': str(e)}
            else:
                response_data = {'message': response.text}
            
            if response.ok:
                return True, response_data
            else:
                print(f"❌ API Error: {method} {response.status_code} - {response_data}")
                return False, response_data
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {str(e)}")
            return False, {'error': str(e)}
    
    def validate_pat(self, pat_token: str) -> Tuple[bool, Dict]:
        """
        Validate PAT by making a test API call
        
        Args:
            pat_token: PAT token to validate
            
        Returns:
            Tuple of (is_valid: bool, response_data: dict)
        """
        success, data = self._make_request('GET', '/rest/api/user/current', pat_token)
        
        if success:
            user_info = data.get('displayName', 'Unknown User')
            print(f"✅ PAT validated for user: {user_info}")
        else:
            print(f"❌ PAT validation failed")
            
        return success, data
    
    def create_pat(self, auth_token: str, name: str, duration_days: int = 45) -> Tuple[bool, Dict]:
        """
        Create a new PAT with specified duration
        
        Args:
            auth_token: Existing valid PAT for authentication
            name: Name for the new PAT
            duration_days: Token validity duration in days
            
        Returns:
            Tuple of (success: bool, pat_data: dict)
        """
        # Try different PAT creation payload formats
        pat_data = {
            'name': name,
            'expirationDuration': duration_days
        }
        
        success, response = self._make_request(
            'POST', 
            '/rest/pat/latest/tokens', 
            auth_token, 
            data=pat_data
        )
        
        # If that fails, try with milliseconds (alternative format)
        if not success and 'duration' in str(response).lower():
            pat_data = {
                'name': name,
                'expirationDuration': duration_days * 24 * 60 * 60 * 1000  # Convert days to milliseconds
            }
            
            success, response = self._make_request(
                'POST', 
                '/rest/pat/latest/tokens', 
                auth_token, 
                data=pat_data
            )
        
        if success:
            if isinstance(response, dict):
                token_id = response.get('id', response.get('tokenId', 'Unknown'))
                new_token = response.get('rawToken', response.get('token', response.get('accessToken', '')))
                expiring_at = response.get('expiringAt', response.get('expiryDate', 'Unknown'))
                
                # Format expiry date
                if expiring_at != 'Unknown' and 'T' in str(expiring_at):
                    try:
                        expires_dt = datetime.fromisoformat(expiring_at.replace('Z', '+00:00'))
                        expiring_at = expires_dt.strftime('%Y-%m-%d')
                    except:
                        pass
                
                print(f"🔧 Created new PAT '{name}' (ID: {token_id}) - Expires: {expiring_at}")
                print(f"🔑 Token: {new_token[:20]}..." if new_token else "🔑 Token not returned")
            else:
                print(f"⚠️  Unexpected response format for PAT creation: {type(response)}")
                print(f"📋 Response: {response}")
        else:
            print(f"❌ Failed to create PAT")
            
        return success, response
    
    def list_pats(self, auth_token: str) -> Tuple[bool, Dict]:
        """
        List all PATs for the authenticated user
        
        Args:
            auth_token: Valid PAT for authentication
            
        Returns:
            Tuple of (success: bool, pats_data: dict)
        """
        success, response = self._make_request('GET', '/rest/pat/latest/tokens', auth_token)
        
        if success:
            # Handle different API response formats
            if isinstance(response, list):
                tokens = response
            elif isinstance(response, dict) and 'tokens' in response:
                tokens = response.get('tokens', [])
            elif isinstance(response, dict):
                tokens = response.get('results', response.get('values', []))
            else:
                tokens = []
            
            print(f"📋 Found {len(tokens)} existing PAT(s)")
            for i, token in enumerate(tokens, 1):
                if isinstance(token, dict):
                    token_id = token.get('id', token.get('tokenId', 'Unknown'))
                    name = token.get('name', token.get('tokenName', 'Unnamed'))
                    expires = token.get('expiringAt', token.get('expiryDate', token.get('expires', 'Never')))
                    
                    # Format expiry date if it's ISO format
                    if expires != 'Never' and 'T' in str(expires):
                        try:
                            expires_dt = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                            expires = expires_dt.strftime('%Y-%m-%d')
                        except:
                            pass
                    
                    print(f"  • {name} (ID: {token_id}) - Expires: {expires}")
        else:
            print(f"❌ Failed to list PATs")
            
        return success, response
    

    def revoke_pat(self, auth_token: str, token_id: str) -> Tuple[bool, Dict]:
        """
        Revoke/delete a specific PAT
        
        Args:
            auth_token: Valid PAT for authentication
            token_id: ID of the token to revoke
            
        Returns:
            Tuple of (success: bool, response_data: dict)
        """
        success, response = self._make_request(
            'DELETE', 
            f'/rest/pat/latest/tokens/{token_id}', 
            auth_token
        )
        
        if success:
            print(f"🗑️  Revoked PAT {token_id}")
        else:
            print(f"❌ Failed to revoke PAT {token_id}")
            
        return success, response
    
    def run_pat_lifecycle_test(self, existing_pat: str, pat_name_prefix: str = 'test-pat', revoke_prefix_pats: bool = False, revoke_pat_id: str = None, revoke_pat_name: str = None) -> bool:
        """
        Run the complete PAT lifecycle test
        
        Args:
            existing_pat: Existing PAT to start with
            pat_name_prefix: Prefix for new PAT name (default: 'test-pat')
            revoke_prefix_pats: Revoke old PATs with the same prefix (recommended)
            revoke_pat_id: ID of specific PAT to revoke (optional)
            revoke_pat_name: Name of specific PAT to revoke (optional)
            
        Returns:
            bool: True if all steps completed successfully
        """
        print("🚀 PAT Lifecycle Test")
        print("=" * 40)
        
        # Track test results
        revocation_attempted = False
        
        # Step 1: Validate existing PAT
        print("\n1️⃣ Validating existing PAT...")
        success, user_data = self.validate_pat(existing_pat)
        if not success:
            print("❌ Cannot proceed - existing PAT is invalid")
            return False
        
        # Step 2: List existing PATs
        print("\n2️⃣ Listing existing PATs...")
        success, pats_data = self.list_pats(existing_pat)
        if not success:
            print("⚠️  Could not list existing PATs, but continuing...")
        
        # Step 3: Create new PAT
        print("\n3️⃣ Creating new PAT...")
        new_pat_name = f"{pat_name_prefix}-{int(time.time())}"
        success, new_pat_data = self.create_pat(existing_pat, new_pat_name, 45)
        if not success:
            print("❌ Cannot proceed - failed to create new PAT")
            return False
        
        # Extract token and ID from response (handle different formats)
        new_pat_token = None
        new_pat_id = None
        
        if isinstance(new_pat_data, dict):
            new_pat_token = new_pat_data.get('rawToken', new_pat_data.get('token', new_pat_data.get('accessToken')))
            new_pat_id = new_pat_data.get('id', new_pat_data.get('tokenId'))
        
        if not new_pat_token:
            print("❌ New PAT token not returned in response")
            print(f"📋 Response data: {new_pat_data}")
            return False
        
        # Step 4: Validate new PAT
        print("\n4️⃣ Validating new PAT...")
        success, _ = self.validate_pat(new_pat_token)
        if not success:
            print("❌ New PAT validation failed")
            return False
        
        # Step 5: Revoke PAT (optional)
        if revoke_prefix_pats or revoke_pat_id or revoke_pat_name:
            print("\n5️⃣ Revoking PAT...")
            
            target_tokens = []
            
            # Strategy 1: Find PATs with matching prefix
            if revoke_prefix_pats:
                print(f"🔍 Looking for PATs with prefix '{pat_name_prefix}'...")
                # Extract tokens from response regardless of format
                tokens = []
                if pats_data:
                    if isinstance(pats_data, list):
                        tokens = pats_data
                    elif isinstance(pats_data, dict):
                        tokens = pats_data.get('tokens', pats_data.get('results', pats_data.get('values', [])))
                
                for token in tokens:
                    if isinstance(token, dict):
                        token_id = token.get('id', token.get('tokenId'))
                        token_name = token.get('name', token.get('tokenName', ''))
                        
                        # Skip the newly created token
                        if str(token_id) == str(new_pat_id):
                            continue
                            
                        # Check if name starts with our prefix
                        if token_name.startswith(pat_name_prefix):
                            target_tokens.append(token)
                            print(f"   Found: {token_name} (ID: {token_id})")
                
            # Strategy 2: Use specific ID or name
            elif revoke_pat_id or revoke_pat_name:
                # Extract tokens from response regardless of format
                tokens = []
                if pats_data:
                    if isinstance(pats_data, list):
                        tokens = pats_data
                    elif isinstance(pats_data, dict):
                        tokens = pats_data.get('tokens', pats_data.get('results', pats_data.get('values', [])))
                
                if tokens:
                    # Find the specific PAT to revoke
                    for token in tokens:
                        if isinstance(token, dict):
                            token_id = token.get('id', token.get('tokenId'))
                            token_name = token.get('name', token.get('tokenName'))
                            
                            # Skip the newly created token
                            if str(token_id) == str(new_pat_id):
                                continue
                                
                            # Check if this matches the target PAT
                            if revoke_pat_id and str(token_id) == str(revoke_pat_id):
                                target_tokens.append(token)
                                break
                            elif revoke_pat_name and token_name == revoke_pat_name:
                                target_tokens.append(token)
                                break
            
            # Attempt revocation if we found targets
            if target_tokens:
                for target_token in target_tokens:
                    target_id = target_token.get('id', target_token.get('tokenId'))
                    target_name = target_token.get('name', target_token.get('tokenName', 'Unknown'))
                    
                    # Safety check: don't revoke the newly created token
                    if str(target_id) == str(new_pat_id):
                        print(f"⚠️  Refusing to revoke newly created PAT '{target_name}' (ID: {target_id})")
                        continue
                    
                    if target_id:
                        revocation_attempted = True
                        success, _ = self.revoke_pat(new_pat_token, target_id)
                        if success:
                            print(f"✅ Successfully revoked PAT '{target_name}' (ID: {target_id})")
                        else:
                            print(f"❌ Failed to revoke PAT '{target_name}' (ID: {target_id})")
            else:
                if revoke_prefix_pats:
                    print(f"ℹ️  No existing PATs found with prefix '{pat_name_prefix}'")
                else:
                    search_criteria = f"ID '{revoke_pat_id}'" if revoke_pat_id else f"name '{revoke_pat_name}'"
                    print(f"⚠️  Could not find PAT with {search_criteria}")
        else:
            print("\n5️⃣ Skipping PAT revocation")
            print("ℹ️  Use --revoke-prefix-pats (recommended) or --revoke-pat-id/--revoke-pat-name for specific targeting")
        
        # Final validation
        print("\n6️⃣ Final validation...")
        final_success, _ = self.validate_pat(new_pat_token)
        
        print("\n" + "=" * 40)
        print("🎉 Test Complete!")
        print(f"🔑 New PAT: {new_pat_token}")
        print(f"📝 PAT ID: {new_pat_id}")
        print("⚠️  Save this token securely!")
        print("=" * 40)
        
        return final_success


def main():
    """Main function to run the PAT management test"""
    parser = argparse.ArgumentParser(description='Confluence/Jira PAT Management Test Script')
    parser.add_argument('--base-url', required=True,
                       help='Base URL of your instance (e.g., https://jira.company.com)')
    parser.add_argument('--existing-pat', required=True,
                       help='Existing PAT token for authentication')
    parser.add_argument('--pat-name-prefix', required=False, default='test-pat',
                       help='Prefix for new PAT name (default: test-pat)')
    parser.add_argument('--revoke-prefix-pats', action='store_true', default=False,
                       help='Revoke old PATs with the same prefix (recommended)')
    parser.add_argument('--revoke-pat-id', required=False,
                       help='ID of specific PAT to revoke (optional)')
    parser.add_argument('--revoke-pat-name', required=False,
                       help='Name of specific PAT to revoke (optional)')
    parser.add_argument('--username', required=False,
                       help='Username (optional)')
    parser.add_argument('--verify-ssl', action='store_true', default=False,
                       help='Enable SSL certificate verification')
    
    args = parser.parse_args()
    
    print("🔧 PAT Management Test")
    print(f"🌐 {args.base_url}")
    print(f"🔑 Using PAT: {args.existing_pat[:20]}...")
    
    # Initialize PAT manager
    pat_manager = PATManager(args.base_url, args.username)
    
    # Run the lifecycle test
    try:
        success = pat_manager.run_pat_lifecycle_test(
            args.existing_pat,
            pat_name_prefix=args.pat_name_prefix,
            revoke_prefix_pats=args.revoke_prefix_pats,
            revoke_pat_id=args.revoke_pat_id,
            revoke_pat_name=args.revoke_pat_name
        )
        if success:
            print("\n✅ All operations completed successfully!")
        else:
            print("\n❌ Some operations failed!")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main() 