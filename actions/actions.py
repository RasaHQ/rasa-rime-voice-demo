from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet


class ActionGetAccountBalance(Action):
    def name(self) -> Text:
        return "action_get_account_balance"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        """Get account balance from mock database."""
        account_type = tracker.get_slot("account_type")

        if account_type:
            account_type = account_type.lower()
            if "check" in account_type:
                account_type = "checking"
            elif "sav" in account_type:
                account_type = "savings"

        balances = {
            "checking": "$2,450.75",
            "savings": "$15,230.00"
        }
        balance = balances.get(account_type, "$0.00")

        return [
            SlotSet("account_type", account_type),
            SlotSet("account_balance", balance)
        ]


class ActionGetAccounts(Action):
    def name(self) -> Text:
        return "action_get_accounts"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        """Get list of user's accounts."""
        return [SlotSet("available_accounts", "checking and savings")]


class ActionProcessTransfer(Action):
    def name(self) -> Text:
        return "action_process_transfer"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        """Process money transfer between accounts."""
        from_account = tracker.get_slot("transfer_from_account")
        to_account = tracker.get_slot("transfer_to_account")
        amount = tracker.get_slot("transfer_amount")

        print(f"Processing transfer: {amount} from {from_account} to {to_account}")
        return []


class ActionBlockCard(Action):
    def name(self) -> Text:
        return "action_block_card"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        """Block a lost or stolen card."""
        card_last_four = tracker.get_slot("card_last_four")

        if not card_last_four:
            return [SlotSet("card_blocked", False)]

        # Clean digits — handles "4 532" or "4 5 3 2" from voice transcription
        cleaned = "".join(c for c in str(card_last_four) if c.isdigit())

        if len(cleaned) != 4:
            print(f"Invalid card digits: {card_last_four!r} (cleaned: {cleaned!r})")
            return [
                SlotSet("card_blocked", False),
                SlotSet("card_last_four", None),
            ]

        print(f"Blocking card ending in {cleaned}")
        return [
            SlotSet("card_blocked", True),
            SlotSet("card_last_four", cleaned),
        ]


class ActionGetTransactions(Action):
    def name(self) -> Text:
        return "action_get_transactions"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        """Get recent transactions (mock)."""
        return []