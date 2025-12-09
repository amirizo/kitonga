# Phone Number Normalization System

## Overview
This system implements comprehensive phone number normalization for the Kitonga Wi-Fi billing system to prevent duplicate users with different phone number formats.

## Problem Solved
Before this implementation, users could create multiple accounts with the same phone number in different formats:
- `+255772236727`
- `255772236727` 
- `0772236727`
- `772236727`

These would be treated as different users, causing confusion and payment issues.

## Solution Implementation

### 1. Phone Number Normalization Functions

**Location:** `billing/utils.py`

#### `normalize_phone_number(phone_number)`
- Converts any Tanzania phone number format to standard `255XXXXXXXXX` format
- Handles formats: `+255`, `255`, `0`, and local numbers
- Raises `ValueError` for invalid formats

#### `validate_tanzania_phone_number(phone_number)`
- Validates phone numbers against actual Tanzania mobile network prefixes
- Returns: `(is_valid, network_name, normalized_number)`
- Supports all major networks: Vodacom, Airtel, Tigo, Zantel, TTCL, Halotel

#### `get_or_create_user(phone_number, **kwargs)`
- Safe wrapper for creating users with normalized phone numbers
- Prevents duplicate creation
- Returns: `(user, created)`

#### `find_user_by_phone(phone_number)`
- Finds users by phone number with automatic normalization
- Returns: `User` instance or `None`

### 2. Model-Level Validation

**Location:** `billing/models.py`

The `User` model now includes:
- `clean()` method that validates and normalizes phone numbers
- Prevention of duplicate phone numbers
- Automatic normalization on save

### 3. Serializer Validation

**Location:** `billing/serializers.py`

All serializers with phone number fields now use:
- `validate_phone_number_field()` for consistent validation
- Automatic normalization before saving
- Proper error messages for invalid formats

### 4. View Updates

**Location:** `billing/views.py`

Updated all views to use the new normalization functions:
- `initiate_payment` - Uses `get_or_create_user()`
- `verify_access` - Uses `find_user_by_phone()`
- `redeem_voucher` - Uses `get_or_create_user()`
- `user_status` - Uses `find_user_by_phone()`
- `list_user_devices` - Uses `find_user_by_phone()`
- `remove_device` - Uses `find_user_by_phone()`
- `mikrotik_auth` - Uses `find_user_by_phone()`

### 5. Data Migration

**Location:** `billing/migrations/0006_normalize_phone_numbers.py`

This migration:
- Normalizes all existing phone numbers
- Merges duplicate users automatically
- Preserves payment history and access rights
- Updates payment records to use normalized phone numbers

### 6. Management Command

**Location:** `billing/management/commands/fix_duplicate_phone_numbers.py`

Features:
- `--dry-run` mode to preview changes
- `--phone` option to fix specific phone number
- Merges duplicate users safely
- Preserves all related data (payments, devices, access logs)

### 7. Testing

**Location:** `test_phone_normalization.py`

Comprehensive test suite that verifies:
- Normalization of various phone number formats
- Proper handling of invalid phone numbers
- Duplicate detection across different formats

## Usage Examples

### API Calls
All these phone number formats will now be treated as the same user:

```bash
# Payment initiation
curl -X POST /api/initiate-payment/ -d '{"phone_number": "+255772236727", "bundle_id": 1}'
curl -X POST /api/initiate-payment/ -d '{"phone_number": "255772236727", "bundle_id": 1}'
curl -X POST /api/initiate-payment/ -d '{"phone_number": "0772236727", "bundle_id": 1}'
curl -X POST /api/initiate-payment/ -d '{"phone_number": "772236727", "bundle_id": 1}'

# All will find/create the same user with phone number: 255772236727
```

### Voucher Redemption
```bash
curl -X POST /api/vouchers/redeem/ -d '{"voucher_code": "ABCD-EFGH-IJKL", "phone_number": "0712345678"}'
# User created/found with normalized phone: 255712345678
```

### User Status Check
```bash
curl /api/user-status/+255712345678/
curl /api/user-status/0712345678/
curl /api/user-status/255712345678/
# All return the same user data
```

## Network Support

The system recognizes these Tanzania mobile networks:

- **Vodacom**: 255752, 255753, 255754, 255755, 255756, 255758, 255759, 255763, 255764, 255765, 255766, 255767
- **Airtel**: 255743, 255744, 255745, 255746, 255747, 255748, 255749, 255732, 255733, 255734, 255735
- **Tigo**: 255714, 255715, 255716, 255717, 255718, 255719, 255712, 255713, 255682, 255683, 255684, 255685, 255686, 255687, 255688, 255689
- **Zantel**: 255777, 255778, 255776
- **TTCL**: 255622, 255623, 255624, 255625, 255626, 255627, 255628, 255629
- **Halotel**: 255729, 255621, 255620

## Deployment Steps

1. **Apply Migration**
   ```bash
   python manage.py migrate billing
   ```

2. **Check for Remaining Duplicates**
   ```bash
   python manage.py fix_duplicate_phone_numbers --dry-run
   ```

3. **Fix Any Remaining Issues** (if needed)
   ```bash
   python manage.py fix_duplicate_phone_numbers
   ```

4. **Test the System**
   ```bash
   python test_phone_normalization.py
   ```

## Benefits

1. **Eliminates Duplicate Users**: One phone number = one user account
2. **Improved User Experience**: Users can enter phone numbers in any format
3. **Consistent Data**: All phone numbers stored in standardized format
4. **Better Analytics**: Accurate user counts and statistics
5. **Payment Reliability**: Prevents payment confusion from multiple accounts
6. **MikroTik Integration**: Seamless authentication regardless of phone format

## Error Handling

The system provides clear error messages for:
- Invalid phone number formats
- Non-Tanzania phone numbers
- Empty or malformed input
- Network validation failures

## Backward Compatibility

- Existing data is preserved during migration
- Old API calls continue to work with automatic normalization
- No breaking changes to existing functionality
- All related records (payments, devices, logs) are maintained

## Testing

Run the test suite to verify functionality:

```bash
cd /path/to/kitonga
python test_phone_normalization.py
```

Expected output: All tests should pass with green checkmarks ✅

## Monitoring

After deployment, monitor:
- User creation rates (should see reduction in duplicates)
- Payment success rates (should improve)
- MikroTik authentication success rates
- API error rates for phone number validation

## Future Enhancements

1. **International Support**: Extend to support other East African countries
2. **Phone Number Verification**: Add SMS verification for phone numbers
3. **Admin Dashboard**: Add UI for managing phone number conflicts
4. **Analytics**: Track phone number format usage patterns
5. **API Documentation**: Update API docs with phone number format examples

---

## Support

For issues or questions about phone number normalization:
1. Check the test results first: `python test_phone_normalization.py`
2. Review migration logs for any errors
3. Use the management command to diagnose: `python manage.py fix_duplicate_phone_numbers --dry-run`
4. Check Django logs for validation errors
