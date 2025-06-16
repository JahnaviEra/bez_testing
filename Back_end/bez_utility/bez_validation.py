import re
from datetime import datetime

def is_valid_client_name(name):
                        return bool(re.fullmatch(r'[A-Za-z0-9 _-]+', name))
                    
class PayloadValidator:
    def __init__(self, data, rules, custom_rules=None):
        self.data = data
        self.rules = rules  # dict: { field: [validations] }
        self.errors = {}
        self.custom_rules = custom_rules or {}

    def is_valid(self):
        self.errors = {}

        for field, validations in self.rules.items():
            value = self.data.get(field)
            
            field_name = field.replace("_"," ").capitalize()
            for validation in validations:
                # Required (not None or empty)
                if validation == "required":
                    if value is None or value == "":
                        self.errors[field] = f"{field_name} is required."
                        break

                elif validation == "not_blank":
                    if isinstance(value, str) and value.strip() == "":
                        self.errors[field] = f"{field_name} cannot be blank."

                elif validation == "alpha":
                    if value and not str(value.replace(" ", "")).isalpha():
                        self.errors[field] = f"{field_name} must contain only letters."
                elif validation == "alpha_num":
                    if value and not is_valid_client_name(value):
                        self.errors[field] = f"{field_name} must contain only letters, numbers, spaces, hyphens, and underscores."
                elif validation == "alpha_num_length":
                    if value and not re.fullmatch(r'[A-Za-z0-9]{4,8}', value):
                        self.errors[field] = f"{field_name} must be 4 to 8 characters long and contain only letters and numbers."
                elif validation == "email":
                    if value and not re.match(r"[^@]+@[^@]+\.[^@]+", value):
                        self.errors[field] = f"{field_name} is not a valid email."

                elif validation == "password":
                    if value:
                        if len(value) < 15:
                            self.errors[field] = f"{field_name} must be at least 15 characters long."
                            continue

                        classes = {
                            "lower": bool(re.search(r"[a-z]", value)),
                            "upper": bool(re.search(r"[A-Z]", value)),
                            "digit": bool(re.search(r"[0-9]", value)),
                            "special": bool(re.search(r"[!@#$%^&*(),.?\":{}|<>]", value))
                        }

                        if sum(classes.values()) < 3:
                            self.errors[field] = (
                                f"{field_name} must contain at least 3 of the 4 character types: "
                                "lowercase, uppercase, digit, special."
                            )
                            continue

                        if re.search(r"(.)\1\1", value):
                            self.errors[field] = f"{field_name} must not contain more than 2 identical characters in a row."

                elif validation == "boolean":
                    if not isinstance(value, bool):
                        self.errors[field] = f"{field_name} must be true or false."

                elif validation == "integer":
                    if not isinstance(value, int):
                        self.errors[field] = f"{field_name} must be an integer."
                
                elif validation == "otp":
                    if not (isinstance(value, (str, int)) and str(value).isdigit() and len(str(value)) == 6):
                        self.errors[field] = f"{field_name} Must be a 6-digit number."

                elif validation == "timestamp":
                    if not self._is_valid_timestamp(value):
                        self.errors[field] = f"{field_name} must be a valid timestamp (ISO or UNIX)."

                elif validation.startswith("choices:"):
                    choices_str = validation.split(":", 1)[1]
                    choices = [item.strip() for item in choices_str.split(",")]
                    if str(value) not in choices:
                        self.errors[field] = f"{field_name} must be one of {choices}."

                elif validation.startswith("min:"):
                    min_len = int(validation.split(":")[1])
                    if isinstance(value, str) and len(value) < min_len:
                        self.errors[field] = f"{field_name} must be at least {min_len} characters."

                elif validation.startswith("max:"):
                    max_len = int(validation.split(":")[1])
                    if isinstance(value, str) and len(value) > max_len:
                        self.errors[field] = f"{field_name} must be at most {max_len} characters."

                # Custom validation hook
                elif validation in self.custom_rules:
                    is_valid, error_message = self.custom_rules[validation](value)
                    if not is_valid:
                        self.errors[field] = error_message

        return len(self.errors) == 0

    def _is_valid_timestamp(self, value):
        # Accept both ISO 8601 and UNIX timestamp
        try:
            if isinstance(value, (int, float)):
                datetime.fromtimestamp(value)
            elif isinstance(value, str):
                datetime.fromisoformat(value)
            else:
                return False
            return True
        except Exception:
            return False


# validation_rules = {
#     "firstname": ["required", "not_blank", "alpha", "min:2", "max:20"],
#     "email": ["required", "email"],
#     "is_active": ["boolean"],
#     "age": ["required", "integer"],
#     "created_at": ["required", "timestamp"],
#     "erp_name": ["required", "choices:quickbooks"],
# }  

# with custom rule

# def no_digits_rule(value):
#     if any(char.isdigit() for char in value):
#         return False, "Value must not contain digits."
#     return True, ""

# # Setup
# custom_validations = {
#     "no_digits": no_digits_rule
# }

# validation_rules = {
#     "firstname": ["required", "no_digits"],
#     "email": ["required", "email"],
#     "password": ["required", "password"]
# }


# validator = PayloadValidator(body, validation_rules)
#         if not validator.is_valid():
#             return {
#                 "statusCode": 400,
#                 "body": json.dumps({"validation_errors": validator.errors})
#             }