import 'package:flutter_test/flutter_test.dart';
import 'package:omnisource/core/utils/validators.dart';

void main() {
  group('Validators detailed', () {
    test('email validator returns specific messages', () {
      expect(Validators.email(''), 'Enter email');
      expect(Validators.email('bad-email'), 'Wrong email');
      expect(Validators.email('valid@test.dev'), isNull);
    });

    test('password validator checks all complexity branches', () {
      expect(Validators.password(''), 'Password is required');
      expect(Validators.password('Ab1!'), 'Minimum 8 characters');
      expect(
        Validators.password('lowercase1!'),
        'Need at least one uppercase letter',
      );
      expect(Validators.password('NoNumber!'), 'Need at least one number');
      expect(
        Validators.password('NoSpecial1'),
        'Need one special character (!@#\$&*)',
      );
      expect(Validators.password('StrongPass1!'), isNull);
    });
  });
}
