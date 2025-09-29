"""Security utilities for API key management"""

import os
import getpass
from typing import Optional

from logger import get_logger

# Optional keyring support
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False


class APIKeyManager:
    """Manages API keys securely using keyring, environment variables, or config"""
    
    SERVICE_NAME = "how-to-cli"
    USERNAME = "openrouter-api-key"
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
    
    def get_api_key(self, config_key: Optional[str] = None) -> Optional[str]:
        """
        Get API key from various sources in order of preference:
        1. Environment variable HOW_API_KEY
        2. Keyring (if available)
        3. Config file
        4. Interactive prompt
        """
        
        # 1. Try environment variable first
        api_key = os.environ.get('HOW_API_KEY')
        if api_key:
            self.logger.debug("API key loaded from environment variable")
            return api_key
        
        # 2. Try keyring if available
        if KEYRING_AVAILABLE:
            try:
                api_key = keyring.get_password(self.SERVICE_NAME, self.USERNAME)
                if api_key:
                    self.logger.debug("API key loaded from keyring")
                    return api_key
            except Exception as e:
                self.logger.debug(f"Failed to get API key from keyring: {e}")
        
        # 3. Try config file
        if config_key:
            self.logger.debug("API key loaded from config file")
            return config_key
        
        # 4. Interactive prompt as last resort
        self.logger.debug("No API key found, prompting user")
        return None
    
    def store_api_key(self, api_key: str, use_keyring: bool = True) -> bool:
        """
        Store API key securely
        
        Args:
            api_key: The API key to store
            use_keyring: Whether to use keyring storage (if available)
        
        Returns:
            True if stored successfully, False otherwise
        """
        if not api_key:
            return False
        
        if use_keyring and KEYRING_AVAILABLE:
            try:
                keyring.set_password(self.SERVICE_NAME, self.USERNAME, api_key)
                self.logger.info("API key stored securely in keyring")
                return True
            except Exception as e:
                self.logger.error(f"Failed to store API key in keyring: {e}")
                return False
        else:
            self.logger.warning("Keyring not available or not requested - API key not stored securely")
            return False
    
    def remove_api_key(self) -> bool:
        """Remove API key from keyring"""
        if KEYRING_AVAILABLE:
            try:
                keyring.delete_password(self.SERVICE_NAME, self.USERNAME)
                self.logger.info("API key removed from keyring")
                return True
            except Exception as e:
                self.logger.debug(f"No API key to remove from keyring: {e}")
                return False
        return False
    
    def prompt_for_api_key(self, store_securely: bool = True) -> Optional[str]:
        """
        Prompt user for API key and optionally store it securely
        
        Args:
            store_securely: Whether to offer to store the key in keyring
        
        Returns:
            The entered API key or None if cancelled
        """
        try:
            print("\n🔑 OpenRouter API Key Required")
            print("You can get your API key from: https://openrouter.ai/keys")
            print("Or set the HOW_API_KEY environment variable to avoid this prompt.")
            
            api_key = getpass.getpass("Enter your OpenRouter API key: ").strip()
            
            if not api_key:
                print("No API key entered.")
                return None
            
            # Validate API key format (basic check)
            if not self._validate_api_key_format(api_key):
                print("⚠️  Warning: API key format doesn't look correct")
                confirm = input("Continue anyway? [y/N]: ").lower().strip()
                if confirm != 'y':
                    return None
            
            # Offer to store securely
            if store_securely and KEYRING_AVAILABLE:
                store = input("\n💾 Store API key securely in system keyring? [Y/n]: ").lower().strip()
                if store != 'n':
                    if self.store_api_key(api_key):
                        print("✅ API key stored securely")
                    else:
                        print("❌ Failed to store API key securely")
            elif store_securely:
                print("ℹ️  Install 'keyring' package to store API keys securely: pip install keyring")
            
            return api_key
            
        except KeyboardInterrupt:
            print("\n\nOperation cancelled.")
            return None
        except Exception as e:
            self.logger.error(f"Error prompting for API key: {e}")
            return None
    
    def _validate_api_key_format(self, api_key: str) -> bool:
        """Basic validation of API key format"""
        # OpenRouter API keys are typically sk-or-... format
        if api_key.startswith('sk-or-') and len(api_key) > 20:
            return True
        
        # Also accept other common formats
        if api_key.startswith('sk-') and len(api_key) > 20:
            return True
        
        return False
    
    def validate_api_key(self, api_key: str) -> bool:
        """
        Validate API key by making a test request
        This should be implemented to make an actual API call
        """
        # This would typically make a lightweight API call to validate
        # For now, just do format validation
        return self._validate_api_key_format(api_key)
    
    def get_storage_info(self) -> dict:
        """Get information about API key storage options"""
        return {
            'keyring_available': KEYRING_AVAILABLE,
            'environment_variable': 'HOW_API_KEY',
            'keyring_service': self.SERVICE_NAME,
            'has_stored_key': bool(KEYRING_AVAILABLE and self._has_stored_key())
        }
    
    def _has_stored_key(self) -> bool:
        """Check if there's a stored key in keyring"""
        if not KEYRING_AVAILABLE:
            return False
        
        try:
            key = keyring.get_password(self.SERVICE_NAME, self.USERNAME)
            return bool(key)
        except Exception:
            return False
