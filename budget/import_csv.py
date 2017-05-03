import re

from difflib import SequenceMatcher
from cliutils import query_yes_no

def build_records(csv_lines):
    """
    This function takes lines from the csv file and normalizes the data
    and returns it in a form we can more readily work with: JSON!!!
    ... Err I mean a simple list of dictionaries ...
    """
    # Creating a list to hold the records will build from the normalized data
    records = []
    for r in csv_lines:
        record = {
            "source_data": {key.lower(): value for (key, value) in zip(headers, r)},
            "category": None,
            "counterparty": None,
            "date": None,
            "bookkeeping_type": None,
            "transaction_type": None,
            }

        record["source_data"]["name_address_string"] = ''

        if record["source_data"]["description"] == "Withdrawal Debit Card W/D":
            record["bookkeeping_type"] = "debit"
            record["transaction_type"] = "debit"
            record["source_data"]["name_address_string"] = record["source_data"]["memo"].split("Date")[0]
        elif record["source_data"]["description"] == "Deposit Home Banking Transfer":
            record["bookkeeping_type"] = "credit"
            record["transaction_type"] = "transfer"
        elif record["source_data"]["description"] == "Deposit KINTETSU WORLD E":
            record["bookkeeping_type"] = "credit"
            record["transaction_type"] = "income"
        elif record["source_data"]["description"] == "Withdrawal Home Banking":
            record["bookkeeping_type"] = "debit"
            record["transaction_type"] = "transfer"
        elif "Withdrawal" in record["source_data"]["description"]:
            record["bookkeeping_type"] = "debit"
            record["transaction_type"] = "credit"
            record["source_data"]["name_address_string"] = " ".join([
                record["source_data"]["description"].replace("Withdrawal ", ""),
                record["source_data"]["memo"].split("%%")[0]])
        elif record["source_data"]["description"] == "Transaction COMMENT":
            break
        elif "Deposit" in record["source_data"]["description"]:
            record["bookkeeping_type"] = "credit"

        record["date"] = record["source_data"]["date"]
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
	return ' '.join(
		[word.capitalize() for word in string.split(' ')])

def guess_formatted_address(address):
    initial_guess = title_caps(address)
    guess_words = []
    for word in initial_guess.split(' '):
        if word in suggestions:
            guess_words.append(suggestions[word])
        else:
            guess_words.append(word)
    guess = ' '.join(guess_words)

    return guess

def check_guess(guess):
    # Asking the user if our guess was right.
    print("Address: {}".format(guess))
    # is_correct = query_yes_no("Is this address correct? ")
    corrected =  input("Enter the properly formated address below.\nDon't enter anything if it's correct: ")
    if corrected == '':
        corrected = guess

    for (original_word, corrected_word) in zip(guess.split(' '), corrected.split(' ')):
    	if original_word != corrected_word and original_word not in suggestions:
    		suggestions[original_word] = corrected_word
    return corrected

def find_counterparty(record, compare_string_length=16):
    compare_string = record["source_data"]["name_address_string"][:compare_string_length]
    final_address = None
    final_counterparty = None
    for counterparty in counterparties:
        similarity = similar(compare_string, counterparty["compare_string"])

        if similarity > 0.5:
            print("Based on {}, this looks like {} ({}). Similarity: {}".format(
                compare_string,
                counterparty["name"],
                counterparty["compare_string"],
                similarity))
            is_match = True if query_yes_no("Is this right? ") == "yes" else False

            if is_match:
                address_guess = guess_formatted_address(get_address(record))

                for address in counterparty["addresses"]:
                    similarity = similar(address_guess, address[:len(address_guess)])
                    if similarity > .5:
                        print("The address is {}.".format(get_address(record)))
                        is_correct_address = True if query_yes_no("Is this {}? ") == "yes" else False
                        if is_correct_address:
                            final_address = address
                            break
                if final_address is None:
                    print("Couldn't seem to find this address in the list...")
                    final_address = check_guess(address_guess)
                break
    return

    # Looping over counterparties to compare by strings
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

suggestions = {
	"Lbj": "LBJ",
	"Fwy": "FWY",
	"Branc": "Branch"
}
