import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

// Core
import 'core/network/api_client.dart';
import 'core/theme/app_theme.dart';

// Data
import 'data/repositories_impl/auth_repository_impl.dart';
import 'data/repositories_impl/analytics_repository_impl.dart';
import 'data/repositories_impl/content_repository_impl.dart';
import 'data/repositories_impl/playlist_repository_impl.dart';

// Domain
import 'domain/repositories/user_repository.dart';
import 'domain/repositories/analytics_repository.dart';
import 'domain/repositories/content_repository.dart';
import 'domain/repositories/playlist_repository.dart';
import 'data/repositories_impl/user_repository_impl.dart';

import 'package:omnisource/domain/repositories/auth_repository.dart';

// Bloc
import 'presentation/bloc/auth/auth_cubit.dart';
import 'presentation/bloc/auth/auth_state.dart';
import 'presentation/bloc/home/home_cubit.dart';
import 'presentation/bloc/search/search_cubit.dart';
import 'presentation/bloc/library/library_cubit.dart';

// Screens
import 'presentation/screens/auth/login_screen.dart';
import 'presentation/screens/onboarding/interests_screen.dart';
import 'presentation/screens/main_layout/main_layout.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  // init ApiClient
  final apiClient = ApiClient();

  runApp(
    // 1. data layer
    MultiRepositoryProvider(
      providers: [
        RepositoryProvider<AuthRepository>(
          create: (context) => AuthRepositoryImpl(apiClient.dio),
        ),
        RepositoryProvider<UserRepository>(
          create: (context) => UserRepositoryImpl(apiClient),
        ),
        RepositoryProvider<ContentRepository>(
          create: (context) => ContentRepositoryImpl(apiClient.dio),
        ),
        RepositoryProvider<AnalyticsRepository>(
          create: (context) => AnalyticsRepositoryImpl(apiClient.dio),
        ),
        RepositoryProvider<PlaylistRepository>(
          create: (context) => PlaylistRepositoryImpl(apiClient.dio),
        ),
      ],
      // 2. cubit layer
      child: MultiBlocProvider(
        providers: [
          BlocProvider(
            create: (context) =>
                AuthCubit(context.read<AuthRepository>())..checkAuth(),
          ),
          BlocProvider(
            create: (context) =>
                HomeCubit(context.read<ContentRepository>())..loadContent(),
          ),
          BlocProvider(
            create: (context) => SearchCubit(
              context.read<ContentRepository>(),
              context.read<AnalyticsRepository>(),
            )..init(),
          ),
          BlocProvider(
            create: (context) => LibraryCubit(
              contentRepository: context.read<ContentRepository>(),
              playlistRepository: context.read<PlaylistRepository>(),
            ),
          ),
        ],
        child: const OmniSourceApp(),
      ),
    ),
  );
}

class OmniSourceApp extends StatelessWidget {
  const OmniSourceApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'OmniSource AI',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.authTheme,
      builder: (context, child) {
        return BlocBuilder<AuthCubit, AuthState>(
          builder: (context, state) {
            final useMainTheme = state is AuthAuthenticated;
            return Theme(
              data: useMainTheme ? AppTheme.mainTheme : AppTheme.authTheme,
              child: DecoratedBox(
                decoration: useMainTheme
                    ? AppTheme.mainBackgroundDecoration
                    : const BoxDecoration(color: AppTheme.authBackground),
                child: child ?? const SizedBox.shrink(),
              ),
            );
          },
        );
      },
      home: BlocListener<AuthCubit, AuthState>(
        listener: (context, state) {
          if (state is AuthAuthenticated && !state.needsOnboarding) {
            context.read<LibraryCubit>().loadLibraryData();
          }
        },
        child: BlocBuilder<AuthCubit, AuthState>(
          builder: (context, state) {
            if (state is AuthAuthenticated) {
              if (state.needsOnboarding) {
                return const InterestsSelectionScreen();
              }
              // if tags already choosed go to main layout
              return const MainLayout();
            }

            // loading spinner
            if (state is AuthLoading) {
              return const Scaffold(
                body: Center(
                  child: CircularProgressIndicator(color: Color(0xFF0984E3)),
                ),
              );
            }

            // if not authorized
            return const LoginScreen();
          },
        ),
      ),
    );
  }
}
