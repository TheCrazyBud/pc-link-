import React, { useState, useEffect, useRef } from 'react';
import { StyleSheet, Text, View, TextInput, TouchableOpacity, ActivityIndicator, Alert, ScrollView, KeyboardAvoidingView, Platform, SafeAreaView, Modal } from 'react-native';
import { Audio } from 'expo-av';
import axios from 'axios';
import { initializeApp } from 'firebase/app';
import { getDatabase, ref, push, serverTimestamp, onValue, query, limitToLast } from 'firebase/database';
import { BlurView } from 'expo-blur';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';

const GROQ_API_KEY = process.env.EXPO_PUBLIC_GROQ_API_KEY;

const firebaseConfig = {
  apiKey: process.env.EXPO_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN,
  databaseURL: process.env.EXPO_PUBLIC_FIREBASE_DATABASE_URL,
  projectId: process.env.EXPO_PUBLIC_FIREBASE_PROJECT_ID,
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const database = getDatabase(app);

const PROJECTS = [
  { label: "Pc Link", value: "PcLink" },
  { label: "QA QuaAnti", value: "QuaAnti" },
  { label: "Texas AI", value: "TexasAi" }
];

// Dynamic systems will be loaded from Firebase

// Android-safe Blur Wrapper
const GlassBackground = ({ intensity = 50, tint = "dark", androidOpacity = 0.4 }) => {
  if (Platform.OS === 'ios') {
    return <BlurView intensity={intensity} tint={tint} style={StyleSheet.absoluteFill} />;
  }
  // Android fallback avoids native crashes caused by expo-blur
  const bgColor = tint === 'light' ? `rgba(255, 255, 255, ${androidOpacity})` : `rgba(0, 0, 0, ${androidOpacity})`;
  return <View style={[StyleSheet.absoluteFill, { backgroundColor: bgColor }]} />;
};

export default function Index() {
  const [recording, setRecording] = useState();
  const [isRecording, setIsRecording] = useState(false);
  const [promptText, setPromptText] = useState('');
  const [systems, setSystems] = useState([]);
  const [selectedSystem, setSelectedSystem] = useState('');
  const [selectedProject, setSelectedProject] = useState('PcLink');
  const [isProcessing, setIsProcessing] = useState(false);
  const [liveLogs, setLiveLogs] = useState([]);
  const [isNavOpen, setIsNavOpen] = useState(false);
  const [showCompletionModal, setShowCompletionModal] = useState(false);
  const scrollViewRef = useRef(null);

  useEffect(() => {
    (async () => {
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission needed', 'Microphone access is required for dictation.');
      }
    })();
  }, []);

  // Listen to active systems in Firebase
  useEffect(() => {
    const sysRef = ref(database, 'systems');
    const unsubscribe = onValue(sysRef, (snapshot) => {
      const data = snapshot.val();
      if (data) {
        const sysArray = Object.values(data);
        setSystems(sysArray);
        // Auto-select first system if none is selected
        if (sysArray.length > 0) {
          setSelectedSystem(prev => prev ? prev : sysArray[0].value);
        }
      } else {
        setSystems([]);
      }
    });
    return () => unsubscribe();
  }, []);

  useEffect(() => {
    if (!selectedSystem) return;
    const logsRef = query(ref(database, `live_logs/${selectedSystem}/${selectedProject}`), limitToLast(50));
    const unsubscribe = onValue(logsRef, (snapshot) => {
      const data = snapshot.val();
      if (data) {
        const logsArray = Object.values(data).sort((a, b) => a.timestamp - b.timestamp);
        if (logsArray.length > 0 && logsArray[logsArray.length - 1].text === '[STATUS: DONE]') {
          const timeDiff = Date.now() - logsArray[logsArray.length - 1].timestamp;
          if (timeDiff < 5000) {
            setShowCompletionModal(true);
          }
        }
        setLiveLogs(logsArray);
      } else {
        setLiveLogs([]);
      }
    });
    return () => unsubscribe();
  }, [selectedSystem, selectedProject]);

  async function startRecording() {
    try {
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });
      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      setRecording(recording);
      setIsRecording(true);
    } catch (err) {
      console.error('Failed to start recording', err);
    }
  }

  async function stopRecording() {
    if (!recording) return;
    setIsRecording(false);
    setIsProcessing(true);
    
    try {
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      await transcribeAudio(uri);
    } catch (err) {
      console.error('Failed to stop recording', err);
    } finally {
      setRecording(undefined);
      setIsProcessing(false);
    }
  }

  async function transcribeAudio(uri) {
    try {
      const formData = new FormData();
      formData.append('file', {
        uri: uri,
        type: 'audio/m4a',
        name: 'dictation.m4a',
      });
      formData.append('model', 'whisper-large-v3');

      const response = await axios.post('https://api.groq.com/openai/v1/audio/transcriptions', formData, {
        headers: {
          'Authorization': `Bearer ${GROQ_API_KEY}`,
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.data && response.data.text) {
        setPromptText((prev) => prev ? `${prev} ${response.data.text}` : response.data.text);
      }
    } catch (error) {
      console.error('Transcription error:', error);
      Alert.alert('Transcription Failed', 'Could not reach Groq API.');
    }
  }

  async function submitTask() {
    if (!promptText.trim()) {
      Alert.alert('Empty Prompt', 'Please dictate or type a task first.');
      return;
    }

    try {
      setIsProcessing(true);
      const queueRef = ref(database, `pending_prompts/${selectedSystem}`);
      await push(queueRef, {
        project: selectedProject,
        prompt: promptText,
        status: 'pending',
        timestamp: serverTimestamp()
      });
      setPromptText('');
    } catch (error) {
      console.error('Database error:', error);
      Alert.alert('Error', 'Failed to push task to the cloud queue.');
    } finally {
      setIsProcessing(false);
    }
  }

  async function submitRetry() {
    try {
      setIsProcessing(true);
      const queueRef = ref(database, `pending_prompts/${selectedSystem}`);
      await push(queueRef, {
        project: selectedProject,
        prompt: "retry",
        status: 'pending',
        timestamp: serverTimestamp()
      });
    } catch (error) {
      console.error('Database error:', error);
      Alert.alert('Error', 'Failed to send retry command.');
    } finally {
      setIsProcessing(false);
    }
  }

  const activeSystemLabel = systems.find(s => s.value === selectedSystem)?.label || "Loading Systems...";
  const activeProjectLabel = PROJECTS.find(p => p.value === selectedProject)?.label || "Select Project";

  return (
    <LinearGradient colors={['#2A1B3D', '#12121A', '#0A0A0F']} style={styles.background}>
      
      {/* Task Completion Modal */}
      <Modal
        animationType="fade"
        transparent={true}
        visible={showCompletionModal}
        onRequestClose={() => setShowCompletionModal(false)}
        statusBarTranslucent={true}
      >
        <View style={styles.modalContainer}>
          <GlassBackground intensity={100} tint="dark" androidOpacity={0.85} />
          <View style={styles.completionContent}>
            <Ionicons name="checkmark-circle" size={100} color="#34C759" />
            <Text style={[styles.title, { marginTop: 24, textAlign: 'center' }]}>Task Completed!</Text>
            <Text style={[styles.subtitle, { textAlign: 'center', marginBottom: 40, fontSize: 16 }]}>
              The AI has finished processing your prompt.
            </Text>
            <TouchableOpacity 
              style={[styles.actionButtonWrapper, { width: '80%', paddingVertical: 16 }]}
              onPress={() => setShowCompletionModal(false)}
              activeOpacity={0.7}
            >
              <GlassBackground intensity={50} tint="light" androidOpacity={0.2} />
              <Text style={[styles.actionButtonText, { fontSize: 16 }]}>Dismiss</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Navigation Modal - Placed outside SafeAreaView to cover the notch */}
      <Modal
        animationType="fade"
        transparent={true}
        visible={isNavOpen}
        onRequestClose={() => setIsNavOpen(false)}
        statusBarTranslucent={true}
      >
        <View style={styles.modalContainer}>
            <GlassBackground intensity={100} tint="dark" androidOpacity={0.85} />
            
            <View style={styles.modalHeader}>
              <TouchableOpacity onPress={() => setIsNavOpen(false)} style={styles.closeBtn}>
                <Ionicons name="close-circle" size={32} color="#ffffff" />
              </TouchableOpacity>
            </View>

            <Text style={[styles.modalTitle, {marginTop: 0}]}>System</Text>
            
            <View style={styles.projectList}>
              {systems.length === 0 ? (
                <Text style={{color: 'rgba(255,255,255,0.5)', marginLeft: 16}}>Waiting for machines...</Text>
              ) : (
                systems.map((sys) => (
                  <TouchableOpacity 
                    key={sys.value} 
                    style={[styles.projectItem, selectedSystem === sys.value && styles.projectItemActive]}
                    onPress={() => setSelectedSystem(sys.value)}
                  >
                    <Text style={[styles.projectItemText, selectedSystem === sys.value && styles.projectItemTextActive]}>
                      {sys.label}
                    </Text>
                    {selectedSystem === sys.value && (
                      <Ionicons name="checkmark" size={24} color="#0A84FF" />
                    )}
                  </TouchableOpacity>
                ))
              )}
            </View>

            <Text style={[styles.modalTitle, {marginTop: 24}]}>Projects</Text>
            
            <View style={styles.projectList}>
              {PROJECTS.map((proj) => (
                <TouchableOpacity 
                  key={proj.value} 
                  style={[styles.projectItem, selectedProject === proj.value && styles.projectItemActive]}
                  onPress={() => {
                    setSelectedProject(proj.value);
                    setIsNavOpen(false);
                  }}
                >
                  <Text style={[styles.projectItemText, selectedProject === proj.value && styles.projectItemTextActive]}>
                    {proj.label}
                  </Text>
                  {selectedProject === proj.value && (
                    <Ionicons name="checkmark" size={24} color="#0A84FF" />
                  )}
                </TouchableOpacity>
              ))}
            </View>
          </View>
        </Modal>

      <SafeAreaView style={styles.safeArea}>
        <KeyboardAvoidingView 
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.container}
        >
          {/* Header */}
          <View style={styles.header}>
            <TouchableOpacity onPress={() => setIsNavOpen(true)} style={styles.menuIcon}>
              <Ionicons name="ellipsis-horizontal-circle" size={32} color="rgba(255, 255, 255, 0.7)" />
            </TouchableOpacity>
            <View style={styles.headerTitles}>
              <Text style={styles.subtitle}>{activeSystemLabel}</Text>
              <Text style={styles.title}>{activeProjectLabel}</Text>
            </View>
          </View>

          {/* Prompt Input Glass Card */}
          <View style={[styles.glassContainer, styles.inputCard]}>
            <GlassBackground intensity={50} tint="dark" />
            <TextInput
              style={styles.textInput}
              multiline
              placeholder="Dictate your prompt here..."
              placeholderTextColor="rgba(255, 255, 255, 0.4)"
              value={promptText}
              onChangeText={setPromptText}
            />
          </View>

          {/* Action Buttons Row */}
          <View style={styles.actionRow}>
            {/* Record Button */}
            <TouchableOpacity 
              style={[styles.actionButtonWrapper, {flex: 1.2}]}
              onPressIn={startRecording}
              onPressOut={stopRecording}
              disabled={isProcessing}
              activeOpacity={0.7}
            >
              <GlassBackground intensity={isRecording ? 80 : 50} tint={isRecording ? "light" : "dark"} />
              <Ionicons name="mic" size={20} color={isRecording ? "#FF3B30" : "#ffffff"} style={{marginBottom: 4}} />
              <Text style={[styles.actionButtonText, isRecording && {color: '#FF3B30'}]}>
                {isRecording ? 'Listening' : 'Speak'}
              </Text>
            </TouchableOpacity>

            {/* Submit Button */}
            <TouchableOpacity 
              style={[styles.actionButtonWrapper, {flex: 1.1}]}
              onPress={submitTask}
              disabled={isProcessing}
              activeOpacity={0.7}
            >
              <GlassBackground intensity={50} tint="dark" />
              {isProcessing ? (
                <ActivityIndicator color="#ffffff" />
              ) : (
                <>
                  <Ionicons name="paper-plane" size={20} color="#34C759" style={{marginBottom: 4}} />
                  <Text style={styles.actionButtonText}>Send</Text>
                </>
              )}
            </TouchableOpacity>

            {/* Retry Button */}
            <TouchableOpacity 
              style={[styles.actionButtonWrapper, {flex: 1}]}
              onPress={submitRetry}
              disabled={isProcessing}
              activeOpacity={0.7}
            >
              <GlassBackground intensity={50} tint="dark" />
              <Ionicons name="refresh" size={20} color="#FF9500" style={{marginBottom: 4}} />
              <Text style={styles.actionButtonText}>Retry</Text>
            </TouchableOpacity>
          </View>

          {/* Telemetry Console */}
          <View style={[styles.glassContainer, styles.consoleCard]}>
            <GlassBackground intensity={50} tint="dark" />
            <View style={styles.consoleHeaderRow}>
              <View style={styles.pulseDot} />
              <Text style={styles.consoleHeader}>LIVE TELEMETRY</Text>
            </View>
            <ScrollView 
              style={styles.consoleScroll}
              contentContainerStyle={{ paddingBottom: 20 }}
              ref={scrollViewRef}
              onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
            >
              {liveLogs.length === 0 ? (
                <Text style={styles.logTextEmpty}>Awaiting instructions...</Text>
              ) : (
                liveLogs.map((log, index) => {
                  if (log.text === '[STATUS: DONE]') {
                    return (
                      <View key={index} style={[styles.glassContainer, styles.doneBanner]}>
                        <GlassBackground intensity={50} tint="light" androidOpacity={0.15} />
                        <Ionicons name="checkmark-circle" size={18} color="#34C759" style={{marginRight: 8}} />
                        <Text style={styles.doneText}>TASK COMPLETED</Text>
                      </View>
                    );
                  }
                  
                  let logStyle = styles.logText;
                  if (log.text.startsWith('👤')) logStyle = [styles.logText, styles.logUser];
                  else if (log.text.startsWith('⚙️')) logStyle = [styles.logText, styles.logTool];
                  else if (log.text.startsWith('💻')) logStyle = [styles.logText, styles.logCmd];
                  else if (log.text.startsWith('📝')) logStyle = [styles.logText, styles.logFile];

                  return (
                    <Text key={index} style={logStyle}>
                      {log.text}
                    </Text>
                  );
                })
              )}
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  background: {
    flex: 1,
  },
  safeArea: {
    flex: 1,
  },
  container: {
    flex: 1,
    padding: 24,
    justifyContent: 'flex-start',
  },
  
  // --- Navigation Modal ---
  modalContainer: {
    flex: 1,
    padding: 32,
    justifyContent: 'center',
  },
  modalHeader: {
    position: 'absolute',
    top: 60,
    right: 24,
    zIndex: 10,
  },
  modalTitle: {
    fontSize: 34,
    fontWeight: '700',
    color: '#ffffff',
    marginBottom: 32,
  },
  projectList: {
    gap: 16,
  },
  projectItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 16,
    paddingHorizontal: 20,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 16,
  },
  projectItemActive: {
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
  },
  projectItemText: {
    fontSize: 18,
    color: '#ffffff',
    fontWeight: '500',
  },
  projectItemTextActive: {
    fontWeight: '700',
    color: '#0A84FF',
  },
  completionContent: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  
  // --- Main Layout ---
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 20,
    marginBottom: 32,
  },
  menuIcon: {
    marginRight: 16,
  },
  headerTitles: {
    flex: 1,
  },
  title: {
    fontSize: 34,
    fontWeight: '700',
    color: '#ffffff',
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 16,
    color: 'rgba(255, 255, 255, 0.6)',
    fontWeight: '600',
    marginBottom: 4,
  },
  
  // --- Glass Cards ---
  glassContainer: {
    borderRadius: 24,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  inputCard: {
    flex: 0.6,
    marginBottom: 20,
  },
  textInput: {
    color: '#ffffff',
    padding: 24,
    height: '100%',
    textAlignVertical: 'top',
    fontSize: 18,
    lineHeight: 28,
    fontWeight: '400',
  },
  
  // --- Action Buttons ---
  actionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 24,
    gap: 12,
  },
  actionButtonWrapper: {
    borderRadius: 20,
    paddingVertical: 18,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.15)',
  },
  actionButtonText: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '600',
  },
  
  // --- Console ---
  consoleCard: {
    flex: 1,
    padding: 24,
  },
  consoleHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  pulseDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#34C759',
    marginRight: 8,
  },
  consoleHeader: {
    color: 'rgba(255, 255, 255, 0.6)',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.5,
  },
  consoleScroll: {
    flex: 1,
  },
  logTextEmpty: {
    color: 'rgba(255, 255, 255, 0.4)',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 13,
    fontStyle: 'italic',
  },
  logText: {
    color: '#E2E8F0',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 12,
    lineHeight: 18,
    marginBottom: 6,
  },
  logUser: { color: '#94A3B8' },
  logTool: { color: '#64D2FF' },
  logCmd: { color: '#BF5AF2' },
  logFile: { color: '#FF375F' },
  doneBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    marginVertical: 16,
    borderWidth: 1,
    borderColor: 'rgba(52, 199, 89, 0.3)',
  },
  doneText: {
    color: '#34C759',
    fontWeight: '800',
    fontSize: 13,
    letterSpacing: 1.5,
  },
});
