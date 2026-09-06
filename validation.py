"""Form validation shared by all creation routes. No browser-only guarantees."""
from datetime import date
from decimal import Decimal, InvalidOperation
import re

VEHICLE_TYPES = ('SUV', 'Sedan', 'Truck', 'Coupe', 'Hatchback', 'Wagon', 'Minivan')
POSITIONS = ('Salesperson', 'Mechanic', 'Manager', 'CEO', 'Security', 'Janitor',
             'Service Advisor', 'Lot Attendant', 'Finance Advisor', 'Parts Specialist', 'Receptionist')
INVENTORY_STATUSES = ('Available', 'Sold', 'Reserved')
APPOINTMENT_STATUSES = ('Scheduled', 'Completed', 'Cancelled', 'Delayed')
SERVICES = ('Brakes', 'Oil Change', 'Tires')
STATES = frozenset('AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC AS GU MP PR VI'.split())
MAX_MONEY = Decimal('99999999.99')


class ValidationError(ValueError):
    """A safe, user-facing message, never raw database details."""


def text(form, name, maximum=100, optional=False):
    value = form.get(name, '').strip()
    if not value and optional:
        return None
    if not value or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise ValidationError(f'{name.replace("_", " ").capitalize()} must contain 1 to {maximum} printable characters.')
    return value


def integer(form, name, minimum=1, maximum=2147483647):
    value = text(form, name, 11)
    if not re.fullmatch(r'[0-9]+', value):
        raise ValidationError(f'{name.replace("_", " ").capitalize()} must be a whole number.')
    number = int(value)
    if not minimum <= number <= maximum:
        raise ValidationError(f'{name.replace("_", " ").capitalize()} must be between {minimum} and {maximum}.')
    return number


def money(form, name, optional=False):
    value = text(form, name, 32, optional)
    if value is None:
        return None
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValidationError(f'{name.replace("_", " ").capitalize()} must be a valid amount.') from None
    if not amount.is_finite() or not Decimal('0') < amount <= MAX_MONEY:
        raise ValidationError(f'{name.replace("_", " ").capitalize()} must be positive and at most {MAX_MONEY}.')
    if amount != amount.quantize(Decimal('0.01')):
        raise ValidationError('Amounts must have no more than two decimal places.')
    return amount


def choice(form, name, allowed):
    value = text(form, name)
    if value not in allowed:
        raise ValidationError(f'Choose a valid {name.replace("_", " ")}.')
    return value


def email(form):
    value = text(form, 'email', 255)
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise ValidationError('Enter a valid email address.')
    return value


def phone(form):
    value = text(form, 'phone', 20, optional=True)
    if value and (not re.fullmatch(r'[+0-9(). -]+', value) or not 7 <= len(re.sub(r'\D', '', value)) <= 15):
        raise ValidationError('Enter a phone number with 7 to 15 digits, or leave it blank.')
    return value


def day(form):
    value = text(form, 'date', 10)
    try:
        result = date.fromisoformat(value)
    except ValueError:
        raise ValidationError('Enter a valid date in YYYY-MM-DD format.') from None
    if result.isoformat() != value or result.year < 1000:
        raise ValidationError('Enter a valid date in YYYY-MM-DD format, year 1000 or later.')
    return result


def values_for(entity, form):
    """Return fields in each INSERT's explicit column order. IDs are database-owned."""
    if entity == 'customers':
        return (text(form, 'name'), integer(form, 'credit', 300, 850), email(form), phone(form), money(form, 'loan', True))
    if entity == 'employees':
        return (text(form, 'name'), phone(form), email(form), choice(form, 'position', POSITIONS), integer(form, 'dealership_id'))
    if entity == 'dealerships':
        state = text(form, 'state', 2).upper()
        zipcode = text(form, 'zipcode', 10)
        if state not in STATES or not re.fullmatch(r'[0-9]{5}(?:-[0-9]{4})?', zipcode):
            raise ValidationError('Enter a valid US state abbreviation and ZIP code.')
        return (text(form, 'address', 255), text(form, 'city'), state, zipcode)
    if entity == 'vehicles':
        return (text(form, 'vin', 50), text(form, 'model'), choice(form, 'type', VEHICLE_TYPES),
                integer(form, 'year', 1886, date.today().year + 1), text(form, 'brand'), integer(form, 'dealership_id'),
                integer(form, 'miles', 0), money(form, 'bought_price'), money(form, 'listing_price'),
                choice(form, 'status', ('Available', 'Reserved')))
    if entity == 'sales':
        return (day(form), integer(form, 'customer_id'), integer(form, 'employee_id'), text(form, 'vin', 50), money(form, 'sold_price'))
    if entity == 'services':
        return (text(form, 'vin', 50), money(form, 'cost'), day(form), choice(form, 'service_done', SERVICES), integer(form, 'employee_id'))
    if entity == 'appointments':
        return (integer(form, 'employee_id'), integer(form, 'customer_id'), text(form, 'vin', 50),
                choice(form, 'status', APPOINTMENT_STATUSES), day(form), integer(form, 'dealership_id'))
    raise ValueError('Unknown entity')
