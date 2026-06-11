import '../../domain/entities/user.dart';
import '../../domain/repositories/user_repository.dart';
import '../models/user_model.dart';
import '../../core/utils/app_logger.dart';
import '../../core/network/api_client.dart';
import '../../core/constants/api_constants.dart';

class UserRepositoryImpl implements UserRepository {
  final ApiClient apiClient;

  UserRepositoryImpl(this.apiClient);

  @override
  Future<User> getMe() async {
    try {
      final response = await apiClient.dio.get(ApiConstants.userMe);
      return UserModel.fromJson(response.data);
    } catch (e, st) {
      AppLogger.error(
        'Get profile failed',
        error: e,
        stackTrace: st,
        name: 'UserRepository',
      );
      rethrow;
    }
  }

  @override
  Future<User> updateProfile({
    String? username,
    List<String>? interests,
  }) async {
    try {
      final response = await apiClient.dio.patch(
        ApiConstants.userUpdate,
        data: <String, dynamic>{'username': username, 'interests': interests}
          ..removeWhere((_, value) => value == null),
      );
      return UserModel.fromJson(response.data);
    } catch (e, st) {
      AppLogger.error(
        'Update profile failed',
        error: e,
        stackTrace: st,
        name: 'UserRepository',
      );
      rethrow;
    }
  }

  @override
  Future<void> deleteAccount() async {
    try {
      await apiClient.dio.delete(ApiConstants.userDelete);
    } catch (e, st) {
      AppLogger.error(
        'Delete account failed',
        error: e,
        stackTrace: st,
        name: 'UserRepository',
      );
      rethrow;
    }
  }
}
