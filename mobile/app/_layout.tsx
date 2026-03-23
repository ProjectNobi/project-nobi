/**
 * Root layout — app entry point.
 * Handles onboarding gate and routes to:
 *   - (tabs) — main tab navigation (Chat | Memories | Settings)
 *   - onboarding — first-time setup (stack, no header)
 */

import React, { useEffect, useState } from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { theme } from '../styles/theme';
import { auth } from '../services/auth';
import { api } from '../services/api';
import { encryption } from '../services/encryption';

export default function RootLayout() {
  const [isReady, setIsReady] = useState(false);
  const [isOnboarded, setIsOnboarded] = useState(false);

  useEffect(() => {
    async function init() {
      try {
        await api.init();
        const user = await auth.init();
        const onboarded = await auth.isOnboarded();
        setIsOnboarded(onboarded);

        if (user) {
          await encryption.init(user.id);
        }
      } catch (err) {
        console.error('Init error:', err);
      } finally {
        setIsReady(true);
      }
    }

    init();
  }, []);

  if (!isReady) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color={theme.colors.primary} />
        <StatusBar style="light" />
      </View>
    );
  }

  return (
    <>
      <StatusBar style="light" />
      <Stack
        initialRouteName={isOnboarded ? '(tabs)' : 'onboarding'}
        screenOptions={{
          headerStyle: { backgroundColor: theme.colors.background },
          headerTintColor: theme.colors.text,
          contentStyle: { backgroundColor: theme.colors.background },
          headerShown: false,
        }}
      >
        {/* Main app — tab navigation */}
        <Stack.Screen
          name="(tabs)"
          options={{ headerShown: false }}
        />
        {/* Onboarding — fullscreen, no tab bar */}
        <Stack.Screen
          name="onboarding"
          options={{
            headerShown: false,
            animation: 'fade',
            // Prevent swipe-back to onboarding once done
            gestureEnabled: false,
          }}
        />
      </Stack>
    </>
  );
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: theme.colors.background,
  },
});
