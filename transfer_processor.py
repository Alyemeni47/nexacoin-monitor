"""
Transfer Processor Module
Handles redistribution of incoming NexaCoin transfers
"""
import logging
import time
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Local package path handling
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# Add libs directory to path for dependencies
LIB_DIR = SCRIPT_DIR / "libs"
if LIB_DIR.exists() and str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

try:
    from solana.publickey import PublicKey
    from solana.transaction import Transaction
    from solana.transaction import AccountMeta
except ImportError as e:
    logging.error(f"Failed to import solana transaction modules: {str(e)}")

try:
    from solders.instruction import Instruction
    from solders.pubkey import Pubkey
except ImportError as e:
    logging.error(f"Failed to import solders modules: {str(e)}")

from solana_client import SolanaClient

logger = logging.getLogger(__name__)

class TransferProcessor:
    """Processes NexaCoin transfers and applies redistribution rules"""
    
    def __init__(self, config, solana_client: SolanaClient):
        """Initialize the transfer processor"""
        self.config = config
        self.solana_client = solana_client
        
        # Redistribution rules
        self.burn_percentage = config.BURN_PERCENTAGE
        self.treasury_percentage = config.TREASURY_PERCENTAGE
        self.fee_percentage = config.FEE_PERCENTAGE
        
        # Destination addresses
        self.burn_address = config.BURN_ADDRESS
        self.treasury_address = config.TREASURY_ADDRESS
        self.fee_address = config.FEE_ADDRESS
        
        logger.info(f"Transfer processor initialized with redistribution rules: "
                   f"Burn: {self.burn_percentage}%, "
                   f"Treasury: {self.treasury_percentage}%, "
                   f"Fee: {self.fee_percentage}%")
                   
    def process_transfer(self, transfer_details: Dict[str, Any]) -> bool:
        """Process an incoming transfer and apply redistribution rules"""
        try:
            amount = transfer_details["amount"]
            destination = transfer_details["destination"]
            transaction_id = transfer_details["transaction_id"]
            
            # Log the incoming transfer
            logger.info(f"Processing transfer: {amount} NexaCoin sent to {destination} "
                       f"(Transaction ID: {transaction_id})")
            
            # Check if the transfer meets the minimum amount threshold
            if amount < self.config.MIN_TRANSFER_AMOUNT:
                logger.info(f"Transfer amount {amount} is below minimum threshold "
                          f"({self.config.MIN_TRANSFER_AMOUNT}). Skipping redistribution.")
                return False
                
            # Calculate redistribution amounts
            burn_amount = int(amount * (self.burn_percentage / 100.0))
            treasury_amount = int(amount * (self.treasury_percentage / 100.0))
            fee_amount = int(amount * (self.fee_percentage / 100.0))
            
            # Ensure we don't exceed the total due to rounding
            total = burn_amount + treasury_amount + fee_amount
            if total > amount:
                # Adjust fee amount to correct for rounding
                fee_amount -= (total - amount)
            
            logger.info(f"Redistribution plan: "
                       f"Burn: {burn_amount}, "
                       f"Treasury: {treasury_amount}, "
                       f"Fee: {fee_amount}")
                       
            # Execute the redistribution
            return self._execute_redistribution(
                destination,
                burn_amount,
                treasury_amount,
                fee_amount
            )
            
        except Exception as e:
            logger.error(f"Error processing transfer: {str(e)}")
            return False
            
    def _execute_redistribution(self, 
                               source_token_account: str, 
                               burn_amount: int, 
                               treasury_amount: int, 
                               fee_amount: int) -> bool:
        """Execute the redistribution transactions"""
        try:
            # Find destination token accounts
            burn_token_account = self._find_token_account_for_owner(self.burn_address)
            treasury_token_account = self._find_token_account_for_owner(self.treasury_address)
            fee_token_account = self._find_token_account_for_owner(self.fee_address)
            
            if not all([burn_token_account, treasury_token_account, fee_token_account]):
                logger.error("Failed to find all required token accounts for redistribution")
                return False
                
            # Create and send the transactions
            transactions = []
            
            # Build burn transaction
            if burn_amount > 0:
                burn_tx = self._build_token_transfer_transaction(
                    source_token_account,
                    burn_token_account,
                    burn_amount
                )
                transactions.append(("Burn", burn_tx, burn_amount))
                
            # Build treasury transaction
            if treasury_amount > 0:
                treasury_tx = self._build_token_transfer_transaction(
                    source_token_account,
                    treasury_token_account,
                    treasury_amount
                )
                transactions.append(("Treasury", treasury_tx, treasury_amount))
                
            # Build fee transaction
            if fee_amount > 0:
                fee_tx = self._build_token_transfer_transaction(
                    source_token_account,
                    fee_token_account,
                    fee_amount
                )
                transactions.append(("Fee", fee_tx, fee_amount))
                
            # Execute all transactions
            success = True
            for tx_type, transaction, amount in transactions:
                try:
                    signature = self.solana_client.send_transaction(transaction)
                    confirmed = self.solana_client.confirm_transaction(
                        signature, 
                        self.config.CONFIRMATION_TIMEOUT
                    )
                    
                    if confirmed:
                        logger.info(f"{tx_type} transaction successful: {amount} NexaCoin, signature: {signature}")
                    else:
                        logger.warning(f"{tx_type} transaction timed out waiting for confirmation")
                        success = False
                        
                except Exception as e:
                    logger.error(f"Error executing {tx_type} transaction: {str(e)}")
                    success = False
                    
                # Add a short delay between transactions
                time.sleep(1)
                
            return success
            
        except Exception as e:
            logger.error(f"Error executing redistribution: {str(e)}")
            return False
            
    def _find_token_account_for_owner(self, owner_address: str) -> Optional[str]:
        """Find a token account that belongs to the given owner and holds NexaCoin"""
        try:
            accounts = self.solana_client.get_token_accounts_by_owner(
                owner_address,
                self.config.NEXACOIN_MINT
            )
            
            if not accounts:
                logger.warning(f"No NexaCoin token accounts found for {owner_address}")
                return None
                
            # Return the first token account
            return str(accounts[0].pubkey)
            
        except Exception as e:
            logger.error(f"Error finding token account for {owner_address}: {str(e)}")
            return None
            
    def _build_token_transfer_transaction(self, source: str, destination: str, amount: int) -> Transaction:
        """Build a token transfer transaction"""
        try:
            # Get recent blockhash
            recent_blockhash = self.solana_client.get_recent_blockhash()
            
            # Create transaction
            transaction = Transaction()
            transaction.recent_blockhash = recent_blockhash
            
            # Add token transfer instruction
            token_program_id = PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
            
            # Structure for Token Program's Transfer instruction
            source_pubkey = PublicKey(source)
            dest_pubkey = PublicKey(destination)
            owner_pubkey = self.solana_client.keypair.public_key
            
            # Create the Transfer instruction
            # Token Program instruction data format for transfer:
            # [3, amount (as u64 LE bytes)]
            amount_bytes = amount.to_bytes(8, byteorder='little')
            data = bytes([3]) + amount_bytes  # 3 is the instruction index for Transfer
            
            # Create the instruction with the correct accounts
            instruction = Instruction(
                program_id=token_program_id,
                accounts=[
                    AccountMeta(pubkey=source_pubkey, is_signer=False, is_writable=True),
                    AccountMeta(pubkey=dest_pubkey, is_signer=False, is_writable=True),
                    AccountMeta(pubkey=owner_pubkey, is_signer=True, is_writable=False)
                ],
                data=data
            )
            
            transaction.add(instruction)
            return transaction
            
        except Exception as e:
            logger.error(f"Error building token transfer transaction: {str(e)}")
            raise
