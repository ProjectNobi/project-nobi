/**
 * Chat screen — main interface for talking with Nori.
 * Full-screen chat with voice input, image sending, and offline support.
 */

import React, { useState, useCallback, useRef } from 'react';
import {
  View,
  TextInput,
  FlatList,
  StyleSheet,
  Pressable,
  Text,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { theme } from '../../styles/theme';
import { useChat } from '../../hooks/useChat';
import { useVoice } from '../../hooks/useVoice';
import { ChatBubble } from '../../components/ChatBubble';
import { TypingIndicator } from '../../components/TypingIndicator';
import { NoriAvatar } from '../../components/NoriAvatar';
import type { Message } from '../../services/api';

export default function ChatScreen() {
  const router = useRouter();
  const [inputText, setInputText] = useState('');
  const flatListRef = useRef<FlatList<Message>>(null);

  const {
    messages,
    isTyping,
    error,
    hasMore,
    sendMessage,
    sendImage,
    retryMessage,
    loadOlderMessages,
  } = useChat();

  const { isAvailable: voiceAvailable, isRecording, toggleRecording } = useVoice();

  // ─── Send text message ─────────────────────────────────────────────────

  const handleSend = useCallback(() => {
    if (!inputText.trim()) return;
    sendMessage(inputText);
    setInputText('');
  }, [inputText, sendMessage]);

  // ─── Pick and send image ───────────────────────────────────────────────

  const handleImagePick = useCallback(async () => {
    try {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission needed', 'Please allow access to your photos to send images.');
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        base64: true,
        quality: 0.7,
        allowsEditing: true,
      });

      if (!result.canceled && result.assets[0]) {
        const asset = result.assets[0];
        if (asset.base64) {
          Alert.prompt(
            'Add a caption',
            'What would you like to ask about this image?',
            [
              { text: 'Skip', onPress: () => sendImage(asset.base64!, '', asset.uri) },
              {
                text: 'Send',
                onPress: (caption) => sendImage(asset.base64!, caption ?? '', asset.uri),
              },
            ],
            'plain-text',
          );
        }
      }
    } catch {
      Alert.alert('Error', 'Failed to pick image');
    }
  }, [sendImage]);

  // ─── Take photo ────────────────────────────────────────────────────────

  const handleCamera = useCallback(async () => {
    try {
      const { status } = await ImagePicker.requestCameraPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission needed', 'Please allow camera access to take photos.');
        return;
      }

      const result = await ImagePicker.launchCameraAsync({
        base64: true,
        quality: 0.7,
        allowsEditing: true,
      });

      if (!result.canceled && result.assets[0]?.base64) {
        const asset = result.assets[0];
        sendImage(asset.base64!, '', asset.uri);
      }
    } catch {
      Alert.alert('Error', 'Failed to take photo');
    }
  }, [sendImage]);

  // ─── Render message ────────────────────────────────────────────────────

  const renderItem = useCallback(
    ({ item }: { item: Message }) => <ChatBubble message={item} onRetry={retryMessage} />,
    [retryMessage],
  );

  const keyExtractor = useCallback((item: Message) => item.id, []);

  // ─── Empty state ───────────────────────────────────────────────────────

  const EmptyChat = () => (
    <View style={styles.emptyContainer}>
      <NoriAvatar size={80} />
      <Text style={styles.emptyTitle}>Hi! I'm Nori 🌸</Text>
      <Text style={styles.emptySubtitle}>
        Your personal AI companion. I remember what matters to you.
      </Text>
      <Text style={styles.emptyHint}>Type a message to start chatting!</Text>
    </View>
  );

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={90}
    >
      {/* Error banner */}
      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>⚠️ {error}</Text>
        </View>
      )}

      {/* Messages list */}
      <FlatList
        ref={flatListRef}
        data={messages}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        inverted
        contentContainerStyle={styles.messageList}
        ListEmptyComponent={EmptyChat}
        ListHeaderComponent={<TypingIndicator visible={isTyping} />}
        onEndReached={hasMore ? loadOlderMessages : undefined}
        onEndReachedThreshold={0.3}
        showsVerticalScrollIndicator={false}
      />

      {/* Input bar */}
      <View style={styles.inputBar}>
        {/* Camera button */}
        <Pressable style={styles.iconButton} onPress={handleCamera}>
          <Text style={styles.iconText}>📷</Text>
        </Pressable>

        {/* Image picker */}
        <Pressable style={styles.iconButton} onPress={handleImagePick}>
          <Text style={styles.iconText}>🖼️</Text>
        </Pressable>

        {/* Text input */}
        <TextInput
          style={styles.input}
          value={inputText}
          onChangeText={setInputText}
          placeholder="Message Nori..."
          placeholderTextColor={theme.colors.textMuted}
          multiline
          maxLength={4000}
          returnKeyType="send"
          onSubmitEditing={handleSend}
          blurOnSubmit={false}
        />

        {/* Voice or Send button */}
        {inputText.trim() ? (
          <Pressable style={styles.sendButton} onPress={handleSend}>
            <Text style={styles.sendIcon}>↑</Text>
          </Pressable>
        ) : voiceAvailable ? (
          <Pressable
            style={[styles.iconButton, isRecording && styles.recordingButton]}
            onPress={toggleRecording}
          >
            <Text style={styles.iconText}>{isRecording ? '⏹️' : '🎤'}</Text>
          </Pressable>
        ) : (
          <Pressable style={styles.sendButton} onPress={handleSend}>
            <Text style={styles.sendIcon}>↑</Text>
          </Pressable>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  headerButtons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  headerBtn: {
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs,
    borderRadius: theme.borderRadius.pill,
    backgroundColor: theme.colors.surface,
  },
  headerBtnText: {
    color: theme.colors.text,
    fontSize: theme.fontSize.sm,
  },
  errorBanner: {
    backgroundColor: 'rgba(255,107,107,0.1)',
    padding: theme.spacing.sm,
    marginHorizontal: theme.spacing.md,
    marginTop: theme.spacing.xs,
    borderRadius: theme.borderRadius.sm,
    borderWidth: 1,
    borderColor: theme.colors.error,
  },
  errorText: {
    color: theme.colors.error,
    fontSize: theme.fontSize.sm,
    textAlign: 'center',
  },
  messageList: {
    paddingVertical: theme.spacing.sm,
    flexGrow: 1,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: theme.spacing.xl,
    // FlatList is inverted, so we need to flip the empty state
    transform: [{ scaleY: -1 }],
    paddingTop: 100,
  },
  emptyTitle: {
    fontSize: theme.fontSize.xl,
    fontWeight: '700',
    color: theme.colors.text,
    marginTop: theme.spacing.lg,
  },
  emptySubtitle: {
    fontSize: theme.fontSize.md,
    color: theme.colors.textSecondary,
    textAlign: 'center',
    marginTop: theme.spacing.sm,
    lineHeight: 22,
  },
  emptyHint: {
    fontSize: theme.fontSize.sm,
    color: theme.colors.textMuted,
    marginTop: theme.spacing.lg,
  },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: theme.spacing.sm,
    borderTopWidth: 1,
    borderTopColor: theme.colors.border,
    backgroundColor: theme.colors.surface,
    gap: theme.spacing.xs,
  },
  iconButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  recordingButton: {
    backgroundColor: theme.colors.error,
  },
  iconText: {
    fontSize: 20,
  },
  input: {
    flex: 1,
    backgroundColor: theme.colors.background,
    borderRadius: theme.borderRadius.xl,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    color: theme.colors.text,
    fontSize: theme.fontSize.md,
    maxHeight: 120,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  sendButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: theme.colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendIcon: {
    color: theme.colors.text,
    fontSize: 20,
    fontWeight: '700',
  },
});
