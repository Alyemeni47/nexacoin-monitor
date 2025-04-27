"""
Configuration module for NexaCoin Monitor Bot
Handles environment variables and default settings
"""
import os
import logging
import sys
from pathlib import Path

# Set up logging first
logger = logging.getLogger(__name__)

# Add the current directory to sys.path for module resolution
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Dictionary to check available modules
available_modules = {}

def check_module(module_name):
    """Check if a module is available and log the result"""
    try:
        __import__(module_name)
        available_modules[module_name] = True
        return True
    except ImportError as e:
        logger.error(f"Module {module_name} is not available: {str(e)}")
        available_modules[module_name] = False
        return False

# Check for base58
base58_available = check_module("base58")
if not base58_available:
    logger.warning("base58 module not found, will use fallback for key handling")

class Config:
    """Configuration class for the NexaCoin Monitor Bot"""
    
    def __init__(self):
        # Network settings
        self.NETWORK_URL = os.getenv("SOLANA_NETWORK_URL", "https://api.mainnet-beta.solana.com")
        self.NETWORK = os.getenv("SOLANA_NETWORK", "mainnet-beta")  # mainnet-beta, testnet, devnet
        
        # Account settings
        self.MONITORED_ACCOUNT = os.getenv("MONITORED_ACCOUNT")
        if not self.MONITORED_ACCOUNT:
            raise ValueError("MONITORED_ACCOUNT environment variable must be set")
            
        # Private key for transaction signing (handle securely)
        self.PRIVATE_KEY_BASE58 = os.getenv("PRIVATE_KEY")
        if not self.PRIVATE_KEY_BASE58:
            raise ValueError("PRIVATE_KEY environment variable must be set")
        
        # Try to decode the private key to verify it's valid
        try:
            import base58
            self.PRIVATE_KEY_BYTES = base58.b58decode(self.PRIVATE_KEY_BASE58)
            logger.debug("Private key loaded successfully")
        except ImportError:
            raise ImportError("Could not import base58 library. Please install it with 'pip install base58==2.1.1'")
        except Exception as e:
            raise ValueError(f"Invalid private key format: {str(e)}")
        
        # NexaCoin token details
        self.NEXACOIN_MINT = os.getenv("NEXACOIN_MINT")
        if not self.NEXACOIN_MINT:
            raise ValueError("NEXACOIN_MINT environment variable must be set")
        
        # Redistribution rules (percentages)
        self.BURN_PERCENTAGE = float(os.getenv("BURN_PERCENTAGE", "5.0"))
        self.TREASURY_PERCENTAGE = float(os.getenv("TREASURY_PERCENTAGE", "70.0"))
        self.FEE_PERCENTAGE = float(os.getenv("FEE_PERCENTAGE", "25.0"))
        
        # Validate percentages
        total_percentage = self.BURN_PERCENTAGE + self.TREASURY_PERCENTAGE + self.FEE_PERCENTAGE
        if abs(total_percentage - 100.0) > 0.01:  # Allow tiny floating point errors
            raise ValueError(f"Redistribution percentages must sum to 100% (got {total_percentage}%)")
            
        # Destination addresses
        self.BURN_ADDRESS = os.getenv("BURN_ADDRESS")
        self.TREASURY_ADDRESS = os.getenv("TREASURY_ADDRESS")
        self.FEE_ADDRESS = os.getenv("FEE_ADDRESS")
        
        if not all([self.BURN_ADDRESS, self.TREASURY_ADDRESS, self.FEE_ADDRESS]):
            raise ValueError("BURN_ADDRESS, TREASURY_ADDRESS, and FEE_ADDRESS must all be set")
        
        # Processing settings
        self.MIN_TRANSFER_AMOUNT = int(os.getenv("MIN_TRANSFER_AMOUNT", "1000"))
        self.MAX_TRANSACTIONS_PER_BATCH = int(os.getenv("MAX_TRANSACTIONS_PER_BATCH", "10"))
        self.CONFIRMATION_TIMEOUT = int(os.getenv("CONFIRMATION_TIMEOUT", "60"))  # seconds
        
        # Polling intervals
        self.POLLING_INTERVAL = float(os.getenv("POLLING_INTERVAL", "10.0"))  # seconds
        self.ERROR_RETRY_INTERVAL = float(os.getenv("ERROR_RETRY_INTERVAL", "30.0"))  # seconds
        
        # Logging
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FILE = os.getenv("LOG_FILE", "nexacoin_monitor.log")
