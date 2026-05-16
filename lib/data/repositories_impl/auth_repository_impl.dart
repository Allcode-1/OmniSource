import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../../core/constants/api_constants.dart';
import '../../core/utils/app_logger.dart';
import '../../domain/entities/user.dart';
import '../../domain/repositories/auth_repository.dart';
import '../models/user_model.dart';

class AuthRepositoryImpl implements AuthRepository {
  final Dio _dio;
  final _storage = const FlutterSecureStorage();

  AuthRepositoryImpl(this._dio);

  @override
  Future<User> login(String email, String password) async {
    try {
      AppLogger.info(
        'Login request started for $email',
        name: 'AuthRepository',
      );
      final response = await _dio.post(
        ApiConstants.login,
        data: {'username': email, 'password': password},
        options: Options(contentType: Headers.formUrlEncodedContentType),
      );

      final token = response.data['access_token']?.toString();
      if (token == null || token.isEmpty) {
        throw Exception('Token is missing in login response');
      }

      await _storage.write(key: 'jwt_token', value: token);
      final refreshToken = response.data['refresh_token']?.toString();
      if (refreshToken != null && refreshToken.isNotEmpty) {
        await _storage.write(key: 'refresh_token', value: refreshToken);
      }
      AppLogger.info('Login successful for $email', name: 'AuthRepository');
      return UserModel.fromJson(response.data['user']);
    } catch (e, st) {
      AppLogger.error(
        'Login failed',
        error: e,
        stackTrace: st,
        name: 'AuthRepository',
      );
      rethrow;
    }
  }

  @override
  Future<User> register(String email, String password, String username) async {
    try {
      AppLogger.info(
        'Register request started for $email',
        name: 'AuthRepository',
      );
      final response = await _dio.post(
        '/auth/register',
        data: {'email': email, 'password': password, 'username': username},
      );
      final token = response.data['access_token']?.toString();
      if (token != null && token.isNotEmpty) {
        await _storage.write(key: 'jwt_token', value: token);
      }
      final refreshToken = response.data['refresh_token']?.toString();
      if (refreshToken != null && refreshToken.isNotEmpty) {
        await _storage.write(key: 'refresh_token', value: refreshToken);
      }

      AppLogger.info('Register successful for $email', name: 'AuthRepository');
      return UserModel.fromJson(response.data['user']);
    } catch (e, st) {
      AppLogger.error(
        'Registration failed',
        error: e,
        stackTrace: st,
        name: 'AuthRepository',
      );
      rethrow;
    }
  }

  @override
  Future<void> completeOnboarding(List<String> tags) async {
    try {
      final token = await _storage.read(key: 'jwt_token');

      await _dio.post(
        '/user/complete-onboarding',
        data: {'interests': tags},
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      AppLogger.info(
        'Onboarding completed with ${tags.length} tags',
        name: 'AuthRepository',
      );
    } catch (e, st) {
      AppLogger.error(
        'Complete onboarding failed',
        error: e,
        stackTrace: st,
        name: 'AuthRepository',
      );
      rethrow;
    }
  }

  @override
  Future<User?> getCurrentUser() async {
    try {
      final token = await _storage.read(key: 'jwt_token');
      if (token == null) return null;
      final response = await _dio.get(
        '/user/me',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      if (response.statusCode == 200) {
        return UserModel.fromJson(response.data);
      }
      return null;
    } catch (e, st) {
      AppLogger.error(
        'Get current user failed',
        error: e,
        stackTrace: st,
        name: 'AuthRepository',
      );
      return null;
    }
  }

  @override
  Future<List<String>> getAvailableTags() async {
    try {
      final response = await _dio.get('/user/tags');

      if (response.statusCode == 200) {
        return List<String>.from(response.data);
      }
      return [];
    } catch (e, st) {
      AppLogger.error(
        'Load tags failed',
        error: e,
        stackTrace: st,
        name: 'AuthRepository',
      );
      return [];
    }
  }

  @override
  Future<void> forgotPassword(String email) async {
    try {
      await _dio.post('/auth/forgot-password', data: {'email': email});
      AppLogger.info(
        'Password reset requested for $email',
        name: 'AuthRepository',
      );
    } catch (e, st) {
      AppLogger.error(
        'Forgot password failed',
        error: e,
        stackTrace: st,
        name: 'AuthRepository',
      );
      rethrow;
    }
  }

  @override
  Future<void> resetPassword(String token, String newPassword) async {
    try {
      final normalizedToken = _normalizeResetToken(token);
      await _dio.post(
        '/auth/reset-password',
        data: {'token': normalizedToken, 'new_password': newPassword},
      );
      AppLogger.info('Password reset completed', name: 'AuthRepository');
    } catch (e, st) {
      AppLogger.error(
        'Reset password failed',
        error: e,
        stackTrace: st,
        name: 'AuthRepository',
      );
      rethrow;
    }
  }

  String _normalizeResetToken(String raw) {
    var token = raw.trim();
    if (token.isEmpty) return '';

    final parsed = Uri.tryParse(token);
    final queryToken = parsed?.queryParameters['token'];
    if (queryToken != null && queryToken.isNotEmpty) {
      token = queryToken;
    }

    return token.replaceAll(RegExp(r'\s+'), '');
  }

  @override
  Future<void> logout() async {
    try {
      await _storage.delete(key: 'jwt_token');
      await _storage.delete(key: 'refresh_token');
      AppLogger.info('Logout successful', name: 'AuthRepository');
    } catch (e, st) {
      AppLogger.error(
        'Logout failed',
        error: e,
        stackTrace: st,
        name: 'AuthRepository',
      );
      rethrow;
    }
  }

  @override
  Future<bool> checkAuth() async {
    try {
      final token = await _storage.read(key: 'jwt_token');
      return token != null;
    } catch (e, st) {
      AppLogger.error(
        'Check auth failed',
        error: e,
        stackTrace: st,
        name: 'AuthRepository',
      );
      return false;
    }
  }
}
