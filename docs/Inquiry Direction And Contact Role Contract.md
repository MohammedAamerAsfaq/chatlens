# Inquiry Direction And Contact Role Contract

## Purpose

Contact classification and message classification are independent concepts. They
must never share values or drive each other implicitly.

## Contact Role

A contact can be labelled exactly as one of:

- `supplier`: the contact sells to us.
- `customer`: the contact buys from us.
- `both`: the contact can be a supplier and a customer.

When a contact is already `both`, an inquiry must not suggest a contact-role
change. This is a final role state, not a message direction.

## Message Direction

Every message has exactly one classification:

- `buy`: the sender is seeking to buy from us.
- `sell`: the sender is offering to sell to us.
- `not_inquiry`: the message is not a trading opportunity.

`buy`, `sell`, and `not_inquiry` are mutually exclusive. A message must never
have direction `both`.

## Invalid Historical Behavior

Earlier code accepted `inquiry_type="both"` and created a buy and sell inquiry
from one message. This was incorrect: it confused the contact-role value
`both` with message direction. The active parser and inquiry-creation paths
now reject message-level `both`; historical records are retained unchanged.

## V2 GatePass

GatePass runs before the existing V2 extraction flow and returns only `buy`,
`sell`, or `not_inquiry`.

- `observational` mode records the decision but always continues V2 processing.
- `enforced` mode continues only `buy` and `sell`; `not_inquiry` ends processing.

GatePass must not create inquiries and must not suggest contact roles. Its
accuracy is measured separately before enforced mode is enabled.
