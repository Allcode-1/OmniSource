import 'package:flutter_test/flutter_test.dart';
import 'package:omnisource/domain/entities/user.dart';
import 'package:omnisource/presentation/bloc/auth/auth_cubit.dart';
import 'package:omnisource/presentation/bloc/auth/auth_state.dart';

import 'test_fakes.dart';

void main() {
  group('AuthCubit', () {
    late FakeAuthRepository repository;
    late AuthCubit cubit;

    final onboardedUser = User(
      id: 'u1',
      email: 'user@test.dev',
      username: 'user',
      isOnboardingCompleted: true,
    );
    final newUser = User(
      id: 'u2',
      email: 'new@test.dev',
      username: 'new',
      isOnboardingCompleted: false,
    );

    setUp(() {
      repository = FakeAuthRepository();
      repository.loginUser = onboardedUser;
      repository.registerUser = newUser;
      cubit = AuthCubit(repository);
    });

    tearDown(() async {
      await cubit.close();
    });

    test('login success emits loading then authenticated', () async {
      final emitted = <AuthState>[];
      final sub = cubit.stream.listen(emitted.add);

      await cubit.login('user@test.dev', 'StrongPass1!');
      await sub.cancel();

      expect(emitted.first, isA<AuthLoading>());
      expect(cubit.state, isA<AuthAuthenticated>());
      final state = cubit.state as AuthAuthenticated;
      expect(state.user.id, 'u1');
      expect(state.needsOnboarding, isFalse);
    });

    test('login failure emits auth error', () async {
      repository.loginError = Exception('invalid credentials');

      await cubit.login('user@test.dev', 'bad');

      expect(cubit.state, isA<AuthError>());
      expect((cubit.state as AuthError).message, contains('Login failed'));
    });

    test('register success sets onboarding flag', () async {
      await cubit.register('new@test.dev', 'StrongPass1!', 'new');

      expect(cubit.state, isA<AuthAuthenticated>());
      final state = cubit.state as AuthAuthenticated;
      expect(state.user.id, 'u2');
      expect(state.needsOnboarding, isTrue);
    });

    test('checkAuth restores user when present', () async {
      repository.currentUser = onboardedUser;

      await cubit.checkAuth();

      expect(cubit.state, isA<AuthAuthenticated>());
      expect((cubit.state as AuthAuthenticated).user.id, 'u1');
    });

    test('checkAuth keeps initial state when no user', () async {
      repository.currentUser = null;

      await cubit.checkAuth();

      expect(cubit.state, isA<AuthInitial>());
    });

    test('forgotPassword returns false and emits error on failure', () async {
      repository.forgotPasswordError = Exception('smtp');

      final result = await cubit.forgotPassword('user@test.dev');

      expect(result, isFalse);
      expect(cubit.state, isA<AuthError>());
    });

    test('resetPassword success returns true and resets state', () async {
      final result = await cubit.resetPassword('token', 'StrongPass1!');

      expect(result, isTrue);
      expect(cubit.state, isA<AuthInitial>());
    });

    test(
      'completeOnboarding emits authenticated when current user exists',
      () async {
        repository.currentUser = onboardedUser;

        await cubit.completeOnboarding(['cyberpunk', 'noir']);

        expect(repository.completeOnboardingCalls, 1);
        expect(repository.lastOnboardingTags, ['cyberpunk', 'noir']);
        expect(cubit.state, isA<AuthAuthenticated>());
        expect((cubit.state as AuthAuthenticated).needsOnboarding, isFalse);
      },
    );

    test(
      'completeOnboarding emits error when user cannot be restored',
      () async {
        repository.currentUser = null;

        await cubit.completeOnboarding(['x']);

        expect(cubit.state, isA<AuthError>());
        expect((cubit.state as AuthError).message, contains('Session expired'));
      },
    );

    test('logout failure emits auth error', () async {
      repository.logoutError = Exception('logout failed');

      await cubit.logout();

      expect(cubit.state, isA<AuthError>());
      expect((cubit.state as AuthError).message, contains('Logout failed'));
    });
  });
}
