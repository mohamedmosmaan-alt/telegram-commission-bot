"""
Conversation states, matching the state machine in the spec (§20).

START -> REQUEST_PHONE -> LOOKUP_CUSTOMER -> (FOUND -> WAIT_FOR_CUSTOMER_MESSAGE)
                                            -> (NOT_FOUND -> back to REQUEST_PHONE)
                                            -> (DUPLICATE -> AWAITING_SECONDARY_ID -> resolved/failed)
"""
REQUEST_PHONE, AWAITING_SECONDARY_ID, WAIT_FOR_CUSTOMER_MESSAGE = range(3)
