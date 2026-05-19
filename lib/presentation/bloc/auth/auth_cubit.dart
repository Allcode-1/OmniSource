import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:dio/dio.dart';
import '../../../core/utils/app_logger.dart';
import '../../../domain/repositories/auth_repository.dart';
import 'auth_state.dart';

class AuthCubit extends Cubit<AuthState> {
  final AuthRepository authRepository;

  AuthCubit(this.authRepository) : super(AuthInitial());

  Future<void> login(String email, String password) async {
    emit(AuthLoading());
    try {
      AppLogger.info('Auth login started for $email', name: 'AuthCubit');
      final user = await authRepository.login(email, password);
      emit(
        AuthAuthenticated(
          user: user,
          needsOnboarding: !user.isOnboardingCompleted,
        ),
      );
      AppLogger.info('Auth login success for $email', name: 'AuthCubit');
    } catch (e, st) {
      AppLogger.error(
        'Auth login failed',
        error: e,
        stackTrace: st,
        name: 'AuthCubit',
      );
      emit(AuthError("Login failed. Check your credentials."));
    }
  }

  Future<void> register(String email, String password, String username) async {
    emit(AuthLoading());
    try {
      AppLogger.info('Auth register started for $email', name: 'AuthCubit');
      final user = await authRepository.register(email, password, username);
      emit(
        AuthAuthenticated(
          user: user,
          needsOnboarding: !user.isOnboardingCompleted,
        ),
      );
      AppLogger.info('Auth register success for $email', name: 'AuthCubit');
    } catch (e, st) {
      AppLogger.error(
        'Auth register failed',
        error: e,
        stackTrace: st,
        name: 'AuthCubit',
      );
      emit(AuthError("Registration failed."));
    }
  }

  Future<void> completeOnboarding(List<String> tags) async {
    final previous = state;
    if (previous is AuthAuthenticated) {
      emit(AuthOnboardingSaving(user: previous.user));
    } else {
      emit(AuthLoading());
    }

    try {
      AppLogger.info('Onboarding completion started', name: 'AuthCubit');
      await authRepository.completeOnboarding(tags);
      final user = await authRepository.getCurrentUser();
      if (user != null) {
        emit(AuthAuthenticated(user: user, needsOnboarding: false));
      } else {
        const message = "Session expired. Please login again.";
        if (previous is AuthAuthenticated) {
          emit(AuthOnboardingFailure(user: previous.user, message: message));
        } else {
          emit(AuthError(message));
        }
      }
    } catch (e, st) {
      AppLogger.error(
        'Onboarding completion failed',
        error: e,
        stackTrace: st,
        name: 'AuthCubit',
      );
      const message = "Failed to save your preferences.";
      if (previous is AuthAuthenticated) {
        emit(AuthOnboardingFailure(user: previous.user, message: message));
      } else {
        emit(AuthError(message));
      }
    }
  }

  Future<void> checkAuth() async {
    try {
      final user = await authRepository.getCurrentUser();
      if (user != null) {
        AppLogger.info('Auth restored from storage', name: 'AuthCubit');
        emit(
          AuthAuthenticated(
            user: user,
            needsOnboarding: !user.isOnboardingCompleted,
          ),
        );
      } else {
        emit(AuthInitial());
      }
    } catch (e, st) {
      AppLogger.error(
        'Auth check failed',
        error: e,
        stackTrace: st,
        name: 'AuthCubit',
      );
      emit(AuthInitial());
    }
  }

  Future<bool> forgotPassword(String email) async {
    emit(AuthLoading());
    try {
      await authRepository.forgotPassword(email);
      emit(AuthInitial());
      return true;
    } catch (e, st) {
      AppLogger.error(
        'Forgot password failed',
        error: e,
        stackTrace: st,
        name: 'AuthCubit',
      );
      emit(AuthError("Failed to send reset email"));
      return false;
    }
  }

  Future<bool> resetPassword(String token, String newPassword) async {
    emit(AuthLoading());
    try {
      await authRepository.resetPassword(token, newPassword);
      emit(AuthInitial());
      return true;
    } catch (e, st) {
      String message = "Invalid token or password reset failed";
      if (e is DioException) {
        final body = e.response?.data;
        if (body is Map && body['detail'] is String) {
          message = body['detail'] as String;
        }
      }
      AppLogger.error(
        'Reset password failed',
        error: e,
        stackTrace: st,
        name: 'AuthCubit',
      );
      emit(AuthError(message));
      return false;
    }
  }

  Future<void> logout() async {
    try {
      await authRepository.logout();
      emit(AuthInitial());
    } catch (e, st) {
      AppLogger.error(
        'Logout failed',
        error: e,
        stackTrace: st,
        name: 'AuthCubit',
      );
      emit(AuthError("Logout failed"));
    }
  }
}
