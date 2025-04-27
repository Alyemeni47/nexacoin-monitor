#!/usr/bin/env python3
"""
NexaCoin Monitor Bot - Main Module
Monitors Solana blockchain for NexaCoin transfers and processes them according to rules
"""
import os
import sys
import time
import logging
import signal
import threading
import json
from pathlib import Path
from flask import Flask, render_template, jsonify, request

# Add current directory to path for easier imports in deployed environment
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# Add libs directory to path for dependencies
LIBS_DIR = SCRIPT_DIR / "libs"
if LIBS_DIR.exists() and str(LIBS_DIR) not in sys.path:
    sys.path.insert(0, str(LIBS_DIR))

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "nexa_coin_monitor_secret")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("nexacoin_monitor.log")
    ]
)

# Setup logger
logger = logging.getLogger(__name__)

# Global variables to store bot status and logs
bot_status = {
    "running": False,
    "last_checked": None,
    "transactions_processed": 0,
    "last_transaction": None,
    "errors": []
}

# In-memory log storage
log_entries = []
MAX_LOG_ENTRIES = 100

# Background thread for the bot
bot_thread = None
stop_bot = threading.Event()

def add_log(level, message):
    """Add a log entry to the in-memory log storage"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_entries.append({
        "timestamp": timestamp,
        "level": level,
        "message": message
    })
    
    # Keep log size under control
    if len(log_entries) > MAX_LOG_ENTRIES:
        log_entries.pop(0)
    
    # Also log to console
    logger.log(getattr(logging, level), message)

def signal_handler(sig, frame):
    """Handle termination signals gracefully"""
    logger.info("Received termination signal. Shutting down...")
    sys.exit(0)

def get_environment_config():
    """Get configuration from environment variables"""
    config = {
        "NETWORK_URL": os.getenv("SOLANA_NETWORK_URL", "https://api.mainnet-beta.solana.com"),
        "NETWORK": os.getenv("SOLANA_NETWORK", "mainnet-beta"),
        "MONITORED_ACCOUNT": os.getenv("MONITORED_ACCOUNT", ""),
        "PRIVATE_KEY": os.getenv("PRIVATE_KEY", ""),
        "NEXACOIN_MINT": os.getenv("NEXACOIN_MINT", ""),
        "BURN_ADDRESS": os.getenv("BURN_ADDRESS", ""),
        "TREASURY_ADDRESS": os.getenv("TREASURY_ADDRESS", ""),
        "FEE_ADDRESS": os.getenv("FEE_ADDRESS", ""),
        "BURN_PERCENTAGE": float(os.getenv("BURN_PERCENTAGE", "5.0")),
        "TREASURY_PERCENTAGE": float(os.getenv("TREASURY_PERCENTAGE", "70.0")),
        "FEE_PERCENTAGE": float(os.getenv("FEE_PERCENTAGE", "25.0")),
        "MIN_TRANSFER_AMOUNT": int(os.getenv("MIN_TRANSFER_AMOUNT", "1000")),
        "POLLING_INTERVAL": float(os.getenv("POLLING_INTERVAL", "10.0")),
        "ERROR_RETRY_INTERVAL": float(os.getenv("ERROR_RETRY_INTERVAL", "30.0"))
    }
    
    # Validate required fields
    missing_fields = []
    for field in ["MONITORED_ACCOUNT", "PRIVATE_KEY", "NEXACOIN_MINT", 
                  "BURN_ADDRESS", "TREASURY_ADDRESS", "FEE_ADDRESS"]:
        if not config[field]:
            missing_fields.append(field)
    
    if missing_fields:
        raise ValueError(f"Missing required configuration: {', '.join(missing_fields)}")
    
    # Validate percentages
    total_percentage = config["BURN_PERCENTAGE"] + config["TREASURY_PERCENTAGE"] + config["FEE_PERCENTAGE"]
    if abs(total_percentage - 100.0) > 0.01:  # Allow tiny floating point errors
        raise ValueError(f"Redistribution percentages must sum to 100% (got {total_percentage}%)")
    
    return config

def simulate_transaction_check(config):
    """
    Simulated transaction check function for demonstration purposes
    In a real implementation, this would query the Solana blockchain
    """
    # Log the check
    add_log("INFO", f"Checking for new transactions on account {config['MONITORED_ACCOUNT']}")
    
    # No actual transactions are checked in this demo
    # In a real implementation, this would query the Solana blockchain
    return False

def simulate_transaction_processing(amount, destination, config):
    """
    Simulated transaction processing for demonstration purposes
    In a real implementation, this would execute Solana transactions
    """
    burn_amount = int(amount * (config["BURN_PERCENTAGE"] / 100.0))
    treasury_amount = int(amount * (config["TREASURY_PERCENTAGE"] / 100.0))
    fee_amount = int(amount * (config["FEE_PERCENTAGE"] / 100.0))
    
    add_log("INFO", f"Processing transfer: {amount} NexaCoin to {destination}")
    add_log("INFO", f"Redistribution plan: Burn: {burn_amount}, Treasury: {treasury_amount}, Fee: {fee_amount}")
    
    # Simulate success
    return True

# Imports for blockchain modules 
# These will be uncommented when deployed to a real environment
# from config import Config
# from solana_client import SolanaClient
# from transaction_monitor import TransactionMonitor
# from transfer_processor import TransferProcessor

def monitor_bot(stop_event=None):
    """
    Main entry point for the NexaCoin Monitor Bot
    
    Args:
        stop_event: A threading.Event that signals when to stop the bot
    """
    try:
        # Only register signal handlers if in the main thread
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        
        # Initialize logging
        add_log("INFO", "Starting NexaCoin Monitor Bot...")
        
        # Load configuration
        try:
            # In the real implementation, we'll use the Config object
            # config = Config()
            # For now, use environment variables dictionary
            config = get_environment_config()
            add_log("INFO", f"Connected to Solana {config['NETWORK_URL']} network")
            add_log("INFO", f"Monitoring account {config['MONITORED_ACCOUNT']} for NexaCoin transfers")
            
            # In real implementation, these would be:
            # solana_client = SolanaClient(config)
            # transfer_processor = TransferProcessor(config, solana_client)
            # transaction_monitor = TransactionMonitor(config, solana_client, transfer_processor)
            
        except Exception as e:
            error_msg = f"Failed to initialize bot components: {str(e)}"
            logger.critical(error_msg)
            add_log("CRITICAL", error_msg)
            if 'bot_status' in globals():
                bot_status["errors"].append(error_msg)
            return 1
        
        # Main loop
        while True:
            # Check if we should stop
            if stop_event and stop_event.is_set():
                add_log("INFO", "Stop event received. Shutting down...")
                break
                
            try:
                # Check for new transactions using simulation function
                found_tx = simulate_transaction_check(config)
                
                # Update the web UI status
                if 'bot_status' in globals():
                    bot_status["last_checked"] = time.strftime("%Y-%m-%d %H:%M:%S")
                
                time.sleep(config["POLLING_INTERVAL"])
            except Exception as e:
                error_msg = f"Error in main monitoring loop: {str(e)}"
                logger.error(error_msg)
                add_log("ERROR", error_msg)
                
                # Update the web UI status
                if 'bot_status' in globals():
                    bot_status["errors"].append(error_msg)
                    
                time.sleep(config["ERROR_RETRY_INTERVAL"])
                
    except Exception as e:
        error_msg = f"Fatal error: {str(e)}"
        logger.critical(error_msg)
        add_log("CRITICAL", error_msg)
        if 'bot_status' in globals():
            bot_status["errors"].append(error_msg)
        return 1
        
    return 0

def run_bot():
    """Function to run the NexaCoin monitor bot in a background thread"""
    global bot_status
    try:
        add_log("INFO", "Starting NexaCoin Monitor Bot in background thread")
        bot_status["running"] = True
        
        # Run the main function with the stop event
        monitor_bot(stop_event=stop_bot)
        
    except Exception as e:
        add_log("ERROR", f"Error running bot: {str(e)}")
        bot_status["errors"].append(str(e))
    finally:
        bot_status["running"] = False
        add_log("INFO", "Bot stopped")

# Flask routes
@app.route('/')
def index():
    """Home page"""
    env_vars_set = all([
        os.environ.get("MONITORED_ACCOUNT"),
        os.environ.get("PRIVATE_KEY"),
        os.environ.get("NEXACOIN_MINT"),
        os.environ.get("BURN_ADDRESS"),
        os.environ.get("TREASURY_ADDRESS"),
        os.environ.get("FEE_ADDRESS")
    ])
    
    return render_template('index.html', 
                           bot_status=bot_status,
                           env_vars_set=env_vars_set)

@app.route('/start_bot', methods=['POST'])
def start_bot_route():
    """Start the bot in a background thread"""
    global bot_thread, stop_bot
    
    if bot_status["running"]:
        return jsonify({"status": "already_running", "message": "Bot is already running"})
    
    # Reset the stop event
    stop_bot = threading.Event()
    
    # Start the bot in a background thread
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    add_log("INFO", "Bot started successfully")
    return jsonify({"status": "started", "message": "Bot started successfully"})

@app.route('/stop_bot', methods=['POST'])
def stop_bot_route():
    """Stop the bot"""
    global stop_bot
    
    if not bot_status["running"]:
        return jsonify({"status": "not_running", "message": "Bot is not running"})
    
    # Signal the bot to stop
    stop_bot.set()
    add_log("INFO", "Stopping bot... (may take a few seconds)")
    
    return jsonify({"status": "stopping", "message": "Bot is stopping"})

@app.route('/logs')
def get_logs():
    """Get the logs for the bot"""
    return jsonify({"logs": log_entries})

@app.route('/status')
def get_status():
    """Get the current status of the bot"""
    return jsonify(bot_status)

@app.route('/config')
def get_config():
    """Get the current configuration (with sensitive data redacted)"""
    try:
        config = get_environment_config()
        
        # Redact sensitive data
        if config.get("PRIVATE_KEY"):
            config["PRIVATE_KEY"] = config["PRIVATE_KEY"][:5] + "..." + config["PRIVATE_KEY"][-5:]
        
        return jsonify({"config": config})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/simulate_transfer', methods=['POST'])
def simulate_transfer():
    """Simulate a transfer for testing"""
    try:
        data = request.json
        amount = int(data.get('amount', 1000))
        destination = data.get('destination', 'simulated_destination')
        
        config = get_environment_config()
        success = simulate_transaction_processing(amount, destination, config)
        
        if success:
            # Update stats
            bot_status["transactions_processed"] += 1
            bot_status["last_transaction"] = {
                "amount": amount,
                "destination": destination,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            return jsonify({
                "status": "success",
                "message": "Simulated transfer processed successfully"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Simulated transfer failed"
            })
    except Exception as e:
        error_msg = str(e)
        add_log("ERROR", f"Error in simulated transfer: {error_msg}")
        return jsonify({
            "status": "error",
            "message": error_msg
        })

@app.route('/test_environment')
def test_environment():
    """Test the environment and report status"""
    results = {
        "flask_running": True,
        "python_version": sys.version,
        "environment_variables": {},
        "required_vars_set": False
    }
    
    # Check environment variables
    required_vars = [
        "MONITORED_ACCOUNT", "PRIVATE_KEY", "NEXACOIN_MINT",
        "BURN_ADDRESS", "TREASURY_ADDRESS", "FEE_ADDRESS"
    ]
    
    for var in required_vars:
        value = os.environ.get(var)
        results["environment_variables"][var] = bool(value)
    
    results["required_vars_set"] = all(results["environment_variables"].values())
    
    return jsonify(results)

# Main entry point
if __name__ == "__main__":
    # If running directly, start the monitoring bot
    sys.exit(monitor_bot())
