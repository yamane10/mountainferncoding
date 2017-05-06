import re
import csv
import json

from difflib import SequenceMatcher
from cliutils import query_yes_no, query_select



def build_records(csv_lines, headers):
    """
    This function takes lines from the csv file and normalizes the data
    and returns it in a form we can more readily work with: JSON!!!
    ... Err I mean a simple list of dictionaries ...
    """
    # Creating a list to hold the records will build from the normalized data
    records = []
    for r in csv_lines:
        # First off, initializing our values
        record = {
            "source_data": {key.lower(): value for (key, value) in zip(headers, r)},
            "category": None,
            "counterparty": None,
            "date": None,
            "bookkeeping_type": None,
            "transaction_type": None,
            }

        record["source_data"]["name_address_string"] = ''
        record["date"] = record["source_data"]["date"]

        # The most surefire way to know what type of transaction it is is based on
        # which amount type in the source data is not ''. We'll use this to split
        # up the transactions and process them further from there.
        if record["source_data"]["amount credit"] != '':
            record["bookkeeping_type"] = "credit"
            record["amount"] = record["source_data"]["amount credit"]

            if record["source_data"]["description"] == "Deposit KINTETSU WORLD E":
                record["transaction_type"] = "income"
                record["counterparty"] = "Kintetsu World Express USA"
                record["address"] = "One Jericho Plaza, Suite 100, Jericho, NY 11753"
            elif (record["source_data"]["description"] == "Deposit Home Banking Transfer" or
                  "Deposit Transfer" in record["source_data"]["description"]):
                record["transaction_type"] = "transfer"
                record["counterparty"] = "Self"
            elif "COP Fee Refund" in record["source_data"]["description"]:
                record["transaction_type"] = "fee refund"
                record["counterparty"] = "EECU"

        elif record["source_data"]["amount debit"] != '':
            record["bookkeeping_type"] = "debit"
            record["amount"] = record["source_data"]["amount debit"]

            if record["source_data"]["description"] == "Withdrawal Debit Card W/D":
                record["transaction_type"] = "debit"
                record["source_data"]["name_address_string"] = record["source_data"]["memo"].split("Date")[0]
            elif record["source_data"]["description"] == "Withdrawal Home Banking":
                record["transaction_type"] = "transfer"
                record["counterparty"] = "Self"
            elif "Withdrawal" in record["source_data"]["description"]:
                record["transaction_type"] = "credit" # The transaction was processed as a credit card purchase.
                record["source_data"]["name_address_string"] = " ".join([
                    record["source_data"]["description"].replace("Withdrawal ", ""),
                    record["source_data"]["memo"].split("%%")[0]])
            elif (record["source_data"]["description"] == "Overdrawn" or
                  record["source_data"]["description"] == "Transfer fee"):
                record["transaction_type"] = "fee"
                record["counterparty"] = "EECU"

        # If it's a transaction comment, we don't want to add it to the list of records.
        if record["source_data"]["description"] == "Transaction COMMENT":
            continue

        # Adding the built record to the list.
        records.append(record)

    return records

def similar(a, b):
        return SequenceMatcher(None, a.upper(), b.upper()).ratio()
def get_counterparty(record):
    try:
        return re.findall("([\D]+)\d+", record["source_data"]["name_address_string"])[0].strip(' -#')
    except:
        print("No counterparty found")
        return None

def get_address(record):
    try:
        address = record["source_data"]["name_address_string"]
    except:
        print("No address found")
        return None
    try:
        nums = re.findall("\d{3,4}", address)
        if len(nums) > 0:
            start = address.index(nums[-1])
        return address[start:].strip(' ')
    except:
        print("No address found")
        return None
def title_caps(string):
    # We have to make sure we are actually working with a string.
    if string is None:
        return None
    return ' '.join(
        [word.capitalize() for word in string.split(' ')])

def guess_formatted(string):
    # We have to make sure we are actually working with a string.
    if string is None:
        return None
    initial_guess = title_caps(string)
    guess_words = []
    for word in initial_guess.split(' '):
        if word in suggestions:
            guess_words.append(suggestions[word])
        else:
            guess_words.append(word)
    guess = ' '.join(guess_words)

    return guess

def check_guess(guess, guess_type="Address"):
    # We have to make sure we are actually working with a string.
    if guess is None:
        return None
    # Asking the user if our guess was right.
    print("{}: {}".format(guess_type.capitalize(), guess))
    # is_correct = query_yes_no("Is this address correct? ")
    corrected =  input(("Enter the properly formated {} below.\n"
        "Don't enter anything if it's correct: ").format(guess_type.lower()))
    if corrected == '':
        corrected = guess

    # Now for any word we guessed wrong, we want to add the guess and corrected
    # word to the suggestions dictionary.
    # REVIEW: This is a really basic way to check, and assumes for the most part
    # that the user isn't going to make many changes and the final string will be
    # almost word for word what the initial guess was. If the user adds any words
    # inbetween the original words the order for checking will be screwed up fast.

    if similar(guess, corrected[:len(guess)]) > .9:
        # Added the if similar clause to so we only check this if the user has
        # only changed simple things like capitalization, etc.
        for (original_word, corrected_word) in zip(
            guess.split(' '),
            corrected[:len(guess)].split(' ')):
            # We only want to check for the length of corrected...
            if original_word != corrected_word and original_word not in suggestions:
                suggestions[original_word] = corrected_word
    return corrected

def find_counterparty(record, compare_string_length=16):
    # We want to make sure to reload the list of counterparties each time we run
    # this function to make sure we're using the most updated list of counterparties.
    # REVIEW: If we change this to an object, we should instead load once,
    # save it as an instance-wide variable, then save at the end of processing
    # the entire list of records to save on system calls.
    counterparties = load_json("counterparties.json")
    if record["source_data"]["name_address_string"] == "":
        record["source_data"]["name_address_string"] = (
            record["source_data"]["description"].replace("Deposit ", "") +
            ' ' + record["source_data"]["memo"])

    compare_string = record["source_data"]["name_address_string"][:compare_string_length]

    final_address = None
    final_counterparty = None

    # For Cash.me payments, we already know a few things:
    if "SQC*" in record["source_data"]["description"]:
        final_address = "1455 Market Street, Suite 600 San Francisco, CA 94103, USA"
        # We know these transaction will have an asterisk after 'SQC' followed by
        # the name of the person who sent the money. Their name will be followed
        # by 'SAN' for San Francisco. We can use this to guess the counterparty
        # and confirm with the user.
        counterparty_guess = title_caps(record["source_data"]["description"].split(
            '*')[1].lower().replace(" san", ''))
        final_counterparty = check_guess(counterparty_guess, guess_type="Counterparty")
        # Only thing we need now is the category.
        category = input("    >>> What's the category for this transaction? ")

    # Looping over counterparties to compare by strings
    for counterparty in counterparties:
        similarity = similar(compare_string, counterparty["compare_string"])
        is_match = False

        if similarity == 1:
            is_match = True # If it's 1.0, pretty sure we've found a match...
        elif similarity > 0.6:
            print("Based on {}, this looks like {} ({}). Similarity: {}".format(
                compare_string,
                counterparty["name"],
                counterparty["compare_string"],
                similarity))
            is_match = True if query_yes_no("Is this right? ") == "yes" else False

        if is_match:
            category = counterparty["category"]
            address_guess = guess_formatted(get_address(record))
            final_counterparty = counterparty["name"]
            try:
                use_default_address = counterparty["use_default_address"]
            except:
                use_default_address = False

            if address_guess is not None and not use_default_address:
                    for address in counterparty["addresses"]:
                        similarity = similar(address_guess, address[:len(address_guess)])
                        if similarity > .5:
                            print("The address from the record is {}.".format(get_address(record)))
                            is_correct_address = True if query_yes_no("Is this {}? ".format(address)) == "yes" else False
                            if is_correct_address:
                                final_address = address
                                break
            if use_default_address:
                final_address = counterparty["default_address"]
            if final_address is None:
                if address_guess is None:
                    print("Couldn't determine the address from the record.\n"
                        "Name_address_string: {}".format(record["source_data"]["name_address_string"]))
                    final_address = input("    >>> What's the address for this transaction? ")
                else:
                    print("Address from the record: {}".format(address_guess))
                    print("Couldn't seem to find this address in the list...")
                    # Let's present the user with the options and ask them to pick an address.
                    choices = [address for address in counterparty["addresses"]] + [address_guess]
                    final_address = query_select(
                        "Which of the following addresses would you like to use?",
                        choices,
                        default=choices[0],
                        multi=False)
                    if final_address == address_guess:
                        final_address = check_guess(address_guess)
                # Now we should check if the user wants to use this address as the defau;t going forward.
                if final_address not in counterparty["addresses"]:
                    counterparty["addresses"].append(final_address)
                set_default = query_yes_no("    >>> Would you like to set this as the deault address? ")
                if set_default == "yes":
                    counterparty["default_address"] = final_address
                    counterparty["use_default_address"] = True
                try:
                    category = counterparty["category"]["name"]
                except:
                    category = input("There was an error getting the category.\n"
                        "    >>> What's the category for this transaction? ")
            break

    if final_counterparty is None:
        # Ok, this means we haven't seen this one before. We need to try to guess the
        # counterparty from the source data and ask the user for final
        # confirmation.
        counterparty_guess = guess_formatted(get_counterparty(record))
        if counterparty_guess is None:
            print("Name_address_string: {}".format(record["source_data"]["name_address_string"]))
            final_counterparty = input("Who's the counterpart for this transaction? ")
            counterparty_guess = ""
        else:
            final_counterparty = check_guess(counterparty_guess, guess_type="Counterparty")
        address_guess = guess_formatted(get_address(record))
        final_address = check_guess(address_guess)

        set_default = "no"
        if final_address is None:
            print("Couldn't determine the address from the record.\n"
                "Name_address_string: {}".format(record["source_data"]["name_address_string"]))
            final_address = input("    >>> What's the address for this transaction? ")
            set_default = query_yes_no("    >>> Would you like to set this as the deault address? ")
            counterparty["addresses"].append(final_address)
        category = input("    >>> What's the category for this transaction? ")
        # Now let's add this counterparty to the growing list.
        counterparty_record = {
            "name": final_counterparty,
            "category": {"name": category},
            "compare_string": compare_string,
            "addresses": [final_address]
        }
        if set_default == "yes":
            counterparty_record["default_address"] = final_address
            counterparty_record["use_default_address"] = True
        else:
            counterparty_record["use_default_address"] = False
        counterparties.append(counterparty_record)

    category = {"name": category} if type(category) == str else category

    # Now let's save the counterparties we'
    save_to_json(counterparties, "counterparties.json")

    return {
        "counterparty": final_counterparty,
        "address": final_address,
        "category": category
        }

def load_json(file):
    with open(file, "r") as f:
	       data = json.load(f)
    return data

def save_to_json(data, filename):
    with open(filename, "w") as f:
        f.seek(0)
        f.truncate()
        json.dump(data, f, indent="    ")

counterparties = [
    {
        "name": "TJ Maxx",
        "category": {
            "name": "clothes",
            "folder": "personal"
        },
        "compare_string": "TJMAXX #0 7735 N",
        "addresses": [
            "7735 N MacArthur Blvd, Irving, TX 75063"
        ]
    },
    {
        "name": "QuikTrip",
        "category": {
            "name": "gas",
            "folder": "transportation"
        },
        "compare_string": "QT 999 08009995 ",
        "addresses": [
            "1600 LBJ FWY Farmers Branch, TX 75234"
        ]
    }
]

categories = [
    {
        "name": "Income",
        "type": "INCOME",
        "": ""
    }
]

recurring = [
    {
        "title": "rent",
        "type": "MONTHLY"
    }
]
