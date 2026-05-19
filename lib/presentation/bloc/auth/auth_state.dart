import '../../../domain/entities/user.dart';

abstract class AuthState {}

class AuthInitial extends AuthState {} // user just launched app

class AuthLoading extends AuthState {} // wait for backend response

class AuthAuthenticated extends AuthState {
  final User user;
  final bool needsOnboarding;
  AuthAuthenticated({required this.user, required this.needsOnboarding});
} // loginned correctly

class AuthOnboardingSaving extends AuthAuthenticated {
  AuthOnboardingSaving({required super.user}) : super(needsOnboarding: true);
}

class AuthOnboardingFailure extends AuthAuthenticated {
  final String message;

  AuthOnboardingFailure({required super.user, required this.message})
    : super(needsOnboarding: true);
}

class AuthError extends AuthState {
  // error (unvalid password or sum)
  final String message;
  AuthError(this.message);
}
