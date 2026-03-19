/**
 * Chat message bubble component.
 * Handles user messages, Nori responses, images, and status indicators.
 */

import React, { useCallback } from 'react';
import {
  View,
  Text,
  Image,
  StyleSheet,
  Pressable,
  ActivityIndicator,
} from 'react-native';
import * as Clipboard from 'expo-clipboard';
import * as Haptics from 'expo-haptics';
import { theme } from '../styles/theme';
import type { Message } from '../services/api';

// ─── Props ───────────────────────────────────────────────────────────────────

interface ChatBubbleProps {
  message: Message;
  onRetry?: (id: string) => void;
}

// ─── Component ───────────────────────────────────────────────────────────────

export function ChatBubble({ message, onRetry }: ChatBubbleProps) {
  const isUser = message.role === 'user';
  const isError = message.status === 'error';
  const isQueued = message.status === 'queued';
  const isSending = message.status === 'sending';

  const handleLongPress = useCallback(async () => {
    await Clipboard.setStringAsync(message.content);
    await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
  }, [message.content]);

  const handleRetry = useCallback(() => {
    if (onRetry && isError) {
      onRetry(message.id);
    }
  }, [onRetry, isError, message.id]);

  const formatTime = (timestamp: number): string => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <View style={[styles.container, isUser ? styles.userContainer : styles.noriContainer]}>
      <Pressable
        onLongPress={handleLongPress}
        onPress={isError ? handleRetry : undefined}
        style={[
          styles.bubble,
          isUser ? styles.userBubble : styles.noriBubble,
          isError && styles.errorBubble,
        ]}
      >
        {/* Image attachment */}
        {message.imageUri && (
          <Image source={{ uri: message.imageUri }} style={styles.image} resizeMode="cover" />
        )}

        {/* Image description from Nori */}
        {message.imageDescription && (
          <Text style={styles.imageDescription}>🔍 {message.imageDescription}</Text>
        )}

        {/* Message content */}
        <Text style={[styles.content, isUser ? styles.userContent : styles.noriContent]}>
          {message.content}
        </Text>

        {/* Footer: time + status */}
        <View style={styles.footer}>
          <Text style={styles.time}>{formatTime(message.timestamp)}</Text>

          {isSending && <ActivityIndicator size="small" color={theme.colors.textMuted} />}
          {isQueued && <Text style={styles.statusIcon}>📤</Text>}
          {isError && <Text style={styles.statusIcon}>⚠️ Tap to retry</Text>}
        </View>
      </Pressable>
    </View>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs,
    width: '100%',
  },
  userContainer: {
    alignItems: 'flex-end',
  },
  noriContainer: {
    alignItems: 'flex-start',
  },
  bubble: {
    maxWidth: '80%',
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm + 2,
    borderRadius: theme.borderRadius.lg,
  },
  userBubble: {
    backgroundColor: theme.colors.userBubble,
    borderBottomRightRadius: theme.spacing.xs,
  },
  noriBubble: {
    backgroundColor: theme.colors.noriBubble,
    borderBottomLeftRadius: theme.spacing.xs,
  },
  errorBubble: {
    borderWidth: 1,
    borderColor: theme.colors.error,
  },
  content: {
    fontSize: theme.fontSize.md,
    lineHeight: 22,
  },
  userContent: {
    color: theme.colors.text,
  },
  noriContent: {
    color: theme.colors.text,
  },
  image: {
    width: 200,
    height: 200,
    borderRadius: theme.borderRadius.md,
    marginBottom: theme.spacing.sm,
  },
  imageDescription: {
    fontSize: theme.fontSize.sm,
    color: theme.colors.textSecondary,
    fontStyle: 'italic',
    marginBottom: theme.spacing.xs,
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    marginTop: theme.spacing.xs,
    gap: theme.spacing.xs,
  },
  time: {
    fontSize: theme.fontSize.xs,
    color: theme.colors.textMuted,
  },
  statusIcon: {
    fontSize: theme.fontSize.xs,
    color: theme.colors.error,
  },
});
