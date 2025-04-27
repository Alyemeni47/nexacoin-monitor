"""
Solana Client Module
Handles communication with the Solana blockchain
"""
import logging
import time
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

# Set up logging first
logger = logging.getLogger(__name__)

# Add the current directory to sys.path for module resolution
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Add libs directory to path for dependencies
LIBS_DIR = SCRIPT_DIR / "libs"
if LIBS_DIR.exists() and str(LIBS_DIR) not in sys.path:
    sys.path.insert(0, str(LIBS_DIR))

# Dictionary to hold module references - makes it easier to mock
# or handle missing modules
modules = {}

# Import helper to centralize error handling
def safe_import(module_name, import_names=None, from_name=None):
    """Safely import a module and log errors"""
    try:
        if from_name:
            # from X import Y
            exec(f"from {from_name} import {', '.join(import_names)}")
            for name in import_names:
                modules[name] = eval(name)
            return True
        else:
            # import X
            exec(f"import {module_name}")
            modules[module_name] = eval(module_name)
            return True
    except ImportError as e:
        logger.error(f"Failed to import {module_name}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error importing {module_name}: {str(e)}")
        return False

# Import base libraries
base58_available = safe_import("base58")

# Import Solana RPC modules
rpc_available = safe_import("solana.rpc.api", ["Client"], "solana.rpc.api")
safe_import("solana.rpc.commitment", ["Commitment"], "solana.rpc.commitment")
safe_import("solana.rpc.types", ["TxOpts"], "solana.rpc.types")
safe_import("solana.exceptions", ["SolanaRpcException"], "solana.exceptions")

# Import Solana core modules
core_available = safe_import("solana.transaction", ["Transaction"], "solana.transaction")
safe_import("solana.publickey", ["PublicKey"], "solana.publickey")
safe_import("solana.keypair", ["Keypair"], "solana.keypair")

# Import Solders modules
solders_available = safe_import("solders.signature", ["Signature"], "solders.signature")
safe_import("solders.message", ["Message"], "solders.message")
safe_import("solders.instruction", ["Instruction"], "solders.instruction")
safe_import("solders.system_program", ["TransferParams", "transfer"], "solders.system_program")

# Log import status
if all([base58_available, rpc_available, core_available, solders_available]):
    logger.info("All Solana modules imported successfully")
else:
    logger.warning("Some Solana modules failed to import, functionality will be limited")

# Now we can define these safely
Client = modules.get("Client")
Commitment = modules.get("Commitment")
TxOpts = modules.get("TxOpts")
Transaction = modules.get("Transaction")
PublicKey = modules.get("PublicKey")
Keypair = modules.get("Keypair")
Signature = modules.get("Signature")
Instruction = modules.get("Instruction")

class SolanaClient:
    """Client for interacting with the Solana blockchain"""
    
    def __init__(self, config):
        """Initialize the Solana client"""
        self.config = config
        self.client = Client(config.NETWORK_URL)
        self.keypair = Keypair.from_secret_key(config.PRIVATE_KEY_BYTES)
        logger.info(f"Initialized Solana client for {config.NETWORK}")
        
    def get_account_info(self, account: str) -> Dict:
        """Get account information"""
        try:
            public_key = PublicKey(account)
            response = self.client.get_account_info(public_key)
            return response
        except Exception as e:
            logger.error(f"Error getting account info for {account}: {str(e)}")
            raise
            
    def get_token_account_balance(self, token_account: str) -> int:
        """Get token account balance"""
        try:
            public_key = PublicKey(token_account)
            response = self.client.get_token_account_balance(public_key)
            if response.value:
                return int(response.value.amount)
            return 0
        except Exception as e:
            logger.error(f"Error getting token balance for {token_account}: {str(e)}")
            raise
            
    def get_token_accounts_by_owner(self, owner: str, token_mint: str) -> List[Dict]:
        """Get token accounts owned by a specific wallet for a specific token mint"""
        try:
            owner_key = PublicKey(owner)
            mint_key = PublicKey(token_mint)
            response = self.client.get_token_accounts_by_owner(
                owner_key, 
                {"mint": mint_key}
            )
            return response.value
        except Exception as e:
            logger.error(f"Error getting token accounts for {owner}: {str(e)}")
            raise
            
    def get_signatures_for_address(self, account: str, before: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get transaction signatures for an account"""
        try:
            public_key = PublicKey(account)
            response = self.client.get_signatures_for_address(
                public_key,
                before=before,
                limit=limit
            )
            return response.value
        except Exception as e:
            logger.error(f"Error getting signatures for {account}: {str(e)}")
            raise
            
    def get_transaction(self, signature: str) -> Dict:
        """Get transaction details"""
        try:
            response = self.client.get_transaction(signature)
            return response.value
        except Exception as e:
            logger.error(f"Error getting transaction {signature}: {str(e)}")
            raise
            
    def send_transaction(self, transaction: Transaction) -> str:
        """Send a transaction to the network"""
        try:
            # Sign the transaction with our keypair
            transaction.sign_partial(self.keypair)
            
            # Send the transaction
            opts = TxOpts(skip_preflight=False, preflight_commitment=Commitment("confirmed"))
            response = self.client.send_transaction(transaction, opts=opts)
            
            if response.value:
                signature = response.value
                logger.info(f"Transaction sent: {signature}")
                return signature
            else:
                error_msg = f"Failed to send transaction: {response}"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
        except Exception as e:
            logger.error(f"Error sending transaction: {str(e)}")
            raise
            
    def confirm_transaction(self, signature: str, timeout: int = 60) -> bool:
        """Wait for a transaction to be confirmed"""
        try:
            sig = Signature.from_string(signature)
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                response = self.client.get_signature_statuses([sig])
                if response.value[0] is not None:
                    confirmed = response.value[0].confirmation_status
                    if confirmed == "confirmed" or confirmed == "finalized":
                        logger.info(f"Transaction {signature} confirmed: {confirmed}")
                        return True
                time.sleep(1)
                
            logger.warning(f"Transaction {signature} not confirmed within timeout")
            return False
            
        except Exception as e:
            logger.error(f"Error confirming transaction {signature}: {str(e)}")
            return False

    def get_recent_blockhash(self) -> str:
        """Get a recent blockhash for transaction construction"""
        try:
            response = self.client.get_recent_blockhash()
            return response.value.blockhash
        except Exception as e:
            logger.error(f"Error getting recent blockhash: {str(e)}")
            raise
