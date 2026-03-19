/**
 * Root layout — navigation setup with dark theme.
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
        // Initialize services
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
        initialRouteName={isOnboarded ? 'index' : 'onboarding'}
        screenOptions={{
          headerStyle: { backgroundColor: theme.colors.background },
          headerTintColor: theme.colors.text,
          headerTitleStyle: { fontWeight: '600' },
          contentStyle: { backgroundColor: theme.colors.background },
          animation: 'slide_from_right',
        }}
      >
        <Stack.Screen
          name="index"
          options={{
            title: 'Nori',
            headerShown: true,
          }}
        />
        <Stack.Screen
          name="memories"
          options={{
            title: 'Memories',
            headerShown: true,
          }}
        />
        <Stack.Screen
          name="settings"
          options={{
            title: 'Settings',
            headerShown: true,
          }}
        />
        <Stack.Screen
          name="onboarding"
          options={{
            headerShown: false,
            animation: 'fade',
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
