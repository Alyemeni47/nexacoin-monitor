"""
Transaction Monitoring Module
Monitors the blockchain for NexaCoin transfer transactions
"""
import logging
import time
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Local package path handling
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# Add libs directory to path for dependencies
LIB_DIR = SCRIPT_DIR / "libs"
if LIB_DIR.exists() and str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

try:
    from solana.publickey import PublicKey
except ImportError:
    logging.error("Failed to import solana.publickey")

from solana_client import SolanaClient
from transfer_processor import TransferProcessor

logger = logging.getLogger(__name__)

class TransactionMonitor:
    """Monitors Solana blockchain for relevant transactions"""
    
    def __init__(self, config, solana_client: SolanaClient, transfer_processor: TransferProcessor):
        """Initialize the transaction monitor"""
        self.config = config
        self.solana_client = solana_client
        self.transfer_processor = transfer_processor
        self.last_signature = None
        self.monitored_account = config.MONITORED_ACCOUNT
        self.nexacoin_mint = config.NEXACOIN_MINT
        
        # Find all token accounts for the monitored account
        self.token_accounts = self._get_monitored_token_accounts()
        
        if not self.token_accounts:
            logger.warning(f"No NexaCoin token accounts found for {self.monitored_account}")
        else:
            logger.info(f"Monitoring {len(self.token_accounts)} NexaCoin token accounts for {self.monitored_account}")
            
    def _get_monitored_token_accounts(self) -> List[str]:
        """Get all token accounts for the monitored wallet that hold NexaCoin"""
        try:
            accounts = self.solana_client.get_token_accounts_by_owner(
                self.monitored_account, 
                self.nexacoin_mint
            )
            
            token_accounts = []
            for account in accounts:
                pubkey = account.pubkey
                token_accounts.append(str(pubkey))
                
            return token_accounts
        except Exception as e:
            logger.error(f"Error getting token accounts: {str(e)}")
            return []
            
    def check_for_new_transactions(self) -> None:
        """Check for new transactions for the monitored account"""
        try:
            # First check the main account
            self._check_account_transactions(self.monitored_account)
            
            # Then check all token accounts
            for token_account in self.token_accounts:
                self._check_account_transactions(token_account)
                
            # Periodically refresh the token accounts list
            if time.time() % 3600 < self.config.POLLING_INTERVAL:  # Roughly once per hour
                new_accounts = self._get_monitored_token_accounts()
                if set(new_accounts) != set(self.token_accounts):
                    logger.info(f"Token accounts updated: {len(new_accounts)} accounts found")
                    self.token_accounts = new_accounts
                    
        except Exception as e:
            logger.error(f"Error checking for new transactions: {str(e)}")
            
    def _check_account_transactions(self, account: str) -> None:
        """Check for new transactions for a specific account"""
        try:
            # Get recent signatures for the account
            signatures = self.solana_client.get_signatures_for_address(
                account, 
                before=self.last_signature,
                limit=20
            )
            
            if not signatures:
                return
                
            # Update the last signature for pagination
            if not self.last_signature:
                self.last_signature = signatures[0]["signature"]
                logger.info(f"Initial signature set to {self.last_signature}")
                return  # Skip processing on first run to establish baseline
                
            # Process transactions in reverse order (oldest first)
            for sig_info in reversed(signatures):
                if sig_info["signature"] == self.last_signature:
                    continue
                    
                # Update the most recent signature
                self.last_signature = signatures[0]["signature"]
                
                # Get full transaction details
                transaction = self.solana_client.get_transaction(sig_info["signature"])
                
                # Process the transaction if it's a NexaCoin transfer
                if transaction and self._is_nexacoin_transfer(transaction):
                    transfer_details = self._extract_transfer_details(transaction)
                    if transfer_details:
                        self.transfer_processor.process_transfer(transfer_details)
                        
        except Exception as e:
            logger.error(f"Error checking transactions for {account}: {str(e)}")
            
    def _is_nexacoin_transfer(self, transaction: Dict[str, Any]) -> bool:
        """Determine if a transaction is a NexaCoin transfer"""
        try:
            # Check if transaction was successful
            if not transaction.get("meta", {}).get("err") is None:
                return False
                
            # Check for token program invocation
            token_program_id = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
            instructions = transaction.get("transaction", {}).get("message", {}).get("instructions", [])
            
            for instruction in instructions:
                # Check if it's a token program and the 3 is a transfer instruction
                if instruction.get("programId") == token_program_id and instruction.get("data", "").startswith("3"):
                    # Check if it involves our NexaCoin mint
                    post_token_balances = transaction.get("meta", {}).get("postTokenBalances", [])
                    pre_token_balances = transaction.get("meta", {}).get("preTokenBalances", [])
                    
                    for balance in post_token_balances + pre_token_balances:
                        if balance.get("mint") == self.nexacoin_mint:
                            return True
                            
            return False
            
        except Exception as e:
            logger.error(f"Error checking if transaction is NexaCoin transfer: {str(e)}")
            return False
            
    def _extract_transfer_details(self, transaction: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract transfer details from a transaction"""
        try:
            # Get pre and post token balances
            pre_balances = {b.get("accountIndex"): b for b in transaction.get("meta", {}).get("preTokenBalances", [])}
            post_balances = {b.get("accountIndex"): b for b in transaction.get("meta", {}).get("postTokenBalances", [])}
            
            # Find accounts where NexaCoin balance increased
            transfer_to = None
            transfer_amount = 0
            
            for idx, post_balance in post_balances.items():
                if post_balance.get("mint") != self.nexacoin_mint:
                    continue
                    
                # This account has NexaCoin - check if balance increased
                pre_amount = int(pre_balances.get(idx, {}).get("uiTokenAmount", {}).get("amount", "0"))
                post_amount = int(post_balance.get("uiTokenAmount", {}).get("amount", "0"))
                
                if post_amount > pre_amount:
                    # This account received NexaCoin
                    account_index = post_balance.get("accountIndex")
                    account_keys = transaction.get("transaction", {}).get("message", {}).get("accountKeys", [])
                    
                    if account_index < len(account_keys):
                        transfer_to = account_keys[account_index]
                        transfer_amount = post_amount - pre_amount
                        
                        # Check if this is a transfer to our monitored account
                        if transfer_to in self.token_accounts:
                            logger.info(f"Detected incoming NexaCoin transfer: {transfer_amount} to {transfer_to}")
                            
                            return {
                                "transaction_id": transaction.get("transaction", {}).get("signatures", [""])[0],
                                "destination": transfer_to,
                                "amount": transfer_amount,
                                "timestamp": transaction.get("blockTime", 0)
                            }
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting transfer details: {str(e)}")
            return None
