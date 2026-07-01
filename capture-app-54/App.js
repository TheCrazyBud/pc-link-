import React, { useState, useEffect, useRef } from 'react';
import { StyleSheet, Text, View, TextInput, TouchableOpacity, ActivityIndicator, Alert, ScrollView, KeyboardAvoidingView, Platform, SafeAreaView, Modal } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Audio } from 'expo-av';
import axios from 'axios';
import { initializeApp } from 'firebase/app';
import { getAuth, signInWithEmailAndPassword, createUserWithEmailAndPassword, onAuthStateChanged, signOut } from 'firebase/auth';
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
const auth = getAuth(app);

// Dynamic systems and projects will be loaded from Firebase

// Android-safe Blur Wrapper
const GlassBackground = ({ intensity = 50, tint = "dark", androidOpacity = 0.4 }) => {
  if (Platform.OS === 'ios') {
    return <BlurView intensity={intensity} tint={tint} style={StyleSheet.absoluteFill} />;
  }
  // Android fallback avoids native crashes caused by expo-blur
  const bgColor = tint === 'light' ? `rgba(255, 255, 255, ${androidOpacity})` : `rgba(0, 0, 0, ${androidOpacity})`;
  return <View style={[StyleSheet.absoluteFill, { backgroundColor: bgColor }]} />;
};

const LogEntry = ({ log }) => {
  const [expanded, setExpanded] = useState(false);
  const isThinking = log.type === 'thinking';
  const isResult = log.type === 'result';
  const isCollapsible = isThinking || (isResult && log.text.length > 200);

  let logStyle = styles.logText;
  if (log.type === 'user') logStyle = [styles.logText, styles.logUser];
  else if (log.type === 'tool_call') logStyle = [styles.logText, styles.logTool];
  else if (log.type === 'status' && log.text.startsWith('💻')) logStyle = [styles.logText, styles.logCmd];
  else if (isThinking) logStyle = [styles.logText, styles.logThinking];
  else if (isResult) logStyle = [styles.logText, styles.logResult];

  const displayText = (isCollapsible && !expanded) 
    ? (isThinking ? "🧠 [Thinking... tap to expand]" : `📋 Result: [${log.text.length} chars... tap to expand]`)
    : log.text;

  if (isCollapsible) {
    return (
      <TouchableOpacity onPress={() => setExpanded(!expanded)} activeOpacity={0.7} style={{marginBottom: 6}}>
        <Text style={logStyle}>{displayText}</Text>
      </TouchableOpacity>
    );
  }

  return <Text style={[logStyle, {marginBottom: 6}]}>{log.text}</Text>;
};

export default function Index() {
  const [user, setUser] = useState(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoginMode, setIsLoginMode] = useState(true);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (u) => {
      setUser(u);
      setAuthLoading(false);
    });
    return () => unsubscribe();
  }, []);

  const handleAuth = async () => {
    if (!email || !password) return Alert.alert('Error', 'Please enter email and password');
    setAuthLoading(true);
    try {
      if (isLoginMode) {
        await signInWithEmailAndPassword(auth, email, password);
      } else {
        await createUserWithEmailAndPassword(auth, email, password);
      }
    } catch (e) {
      Alert.alert('Auth Error', e.message);
    }
    setAuthLoading(false);
  };

  const [recording, setRecording] = useState();
  const [isRecording, setIsRecording] = useState(false);
  const [promptText, setPromptText] = useState('');
  const [systems, setSystems] = useState([]);
  const [selectedSystem, setSelectedSystem] = useState('');
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [liveLogs, setLiveLogs] = useState([]);
  const [isNavOpen, setIsNavOpen] = useState(false);
  const [showCompletionModal, setShowCompletionModal] = useState(false);
  const scrollViewRef = useRef(null);

  // Terminal States
  const [activeTab, setActiveTab] = useState('vibe'); // 'vibe' | 'terminals'
  const [terminals, setTerminals] = useState([]);
  const [selectedTerminal, setSelectedTerminal] = useState('');
  const [terminalLogs, setTerminalLogs] = useState([]);
  const [terminalInput, setTerminalInput] = useState('');
  const terminalScrollRef = useRef(null);
  const [lastPrompt, setLastPrompt] = useState('');

  // Load last prompt from AsyncStorage when project changes
  useEffect(() => {
    if (!selectedProject) return;
    AsyncStorage.getItem(`lastPrompt_${selectedProject}`).then(val => {
      setLastPrompt(val || '');
    });
  }, [selectedProject]);

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
    const sysRef = ref(database, `users/${user.uid}/systems`);
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

  // Listen to projects for the selected system
  useEffect(() => {
    if (!selectedSystem) return;
    const projRef = ref(database, `users/${user.uid}/systems/${selectedSystem}/projects`);
    const unsubscribe = onValue(projRef, (snapshot) => {
      const data = snapshot.val();
      if (data) {
        const projArray = Object.values(data);
        setProjects(projArray);
        // Auto-select first project if current selection is not in the new list
        setSelectedProject(prev => {
          if (prev && projArray.some(p => p.value === prev)) return prev;
          return projArray.length > 0 ? projArray[0].value : '';
        });
      } else {
        setProjects([]);
      }
    });
    return () => unsubscribe();
  }, [selectedSystem]);

  useEffect(() => {
    if (!selectedSystem) return;
    const logsRef = query(ref(database, `users/${user.uid}/live_logs/${selectedSystem}/${selectedProject}`), limitToLast(200));
    const unsubscribe = onValue(logsRef, (snapshot) => {
      const data = snapshot.val();
      if (data) {
        const rawLogs = Object.values(data).sort((a, b) => a.timestamp - b.timestamp);
        
        // Reassemble chunked logs
        const groupedLogs = [];
        const chunkMap = {};
        
        for (const log of rawLogs) {
          if (log.chunk_group) {
            if (!chunkMap[log.chunk_group]) {
              chunkMap[log.chunk_group] = [];
            }
            chunkMap[log.chunk_group].push(log);
          } else {
            groupedLogs.push(log);
          }
        }
        
        for (const groupId in chunkMap) {
          const chunks = chunkMap[groupId];
          chunks.sort((a, b) => (a.chunk_index || 0) - (b.chunk_index || 0));
          const assembledLog = { ...chunks[0] };
          assembledLog.text = chunks.map(c => c.text).join('');
          groupedLogs.push(assembledLog);
        }
        
        groupedLogs.sort((a, b) => a.timestamp - b.timestamp);

        if (groupedLogs.length > 0 && groupedLogs[groupedLogs.length - 1].type === 'status' && groupedLogs[groupedLogs.length - 1].text === '[STATUS: DONE]') {
          const timeDiff = Date.now() - groupedLogs[groupedLogs.length - 1].timestamp;
          if (timeDiff < 5000) {
            setShowCompletionModal(true);
          }
        }
        setLiveLogs(groupedLogs);
      } else {
        setLiveLogs([]);
      }
    });
    return () => unsubscribe();
  }, [selectedSystem, selectedProject]);

  // Listen to Active Terminals - scoped by selectedProject to prevent cross-project bleed
  useEffect(() => {
    if (!selectedSystem || !selectedProject) return;
    setTerminals([]);
    setSelectedTerminal('');
    const termRef = ref(database, `users/${user.uid}/remote_terminals/${selectedSystem}/${selectedProject}/active`);
    const unsubscribe = onValue(termRef, (snapshot) => {
      const data = snapshot.val();
      if (data) {
        const termsArray = Object.keys(data).map(key => ({
          id: key,
          ...data[key]
        }));
        setTerminals(termsArray);
        if (termsArray.length > 0) {
          setSelectedTerminal(prev => prev ? prev : termsArray[0].id);
        }
      } else {
        setTerminals([]);
        setSelectedTerminal('');
      }
    });
    return () => unsubscribe();
  }, [selectedSystem, selectedProject]);

  // Listen to Selected Terminal Logs - scoped by selectedProject
  useEffect(() => {
    if (!selectedSystem || !selectedProject || !selectedTerminal) {
        setTerminalLogs([]);
        return;
    }
    const logsRef = query(ref(database, `users/${user.uid}/remote_terminals/${selectedSystem}/${selectedProject}/${selectedTerminal}/logs`), limitToLast(100));
    const unsubscribe = onValue(logsRef, (snapshot) => {
      const data = snapshot.val();
      if (data) {
        const logsArray = Object.values(data).sort((a, b) => a.timestamp - b.timestamp);
        setTerminalLogs(logsArray);
      } else {
        setTerminalLogs([]);
      }
    });
    return () => unsubscribe();
  }, [selectedSystem, selectedProject, selectedTerminal]);

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
      const queueRef = ref(database, `users/${user.uid}/pending_prompts/${selectedSystem}`);
      await push(queueRef, {
        project: selectedProject,
        prompt: promptText,
        status: 'pending',
        timestamp: serverTimestamp()
      });
      // Save last prompt per project
      setLastPrompt(promptText);
      AsyncStorage.setItem(`lastPrompt_${selectedProject}`, promptText);
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
      const queueRef = ref(database, `users/${user.uid}/pending_prompts/${selectedSystem}`);
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

  async function spawnTerminal() {
    try {
      setIsProcessing(true);
      const queueRef = ref(database, `users/${user.uid}/remote_terminals/${selectedSystem}/control`);
      await push(queueRef, {
        type: 'spawn',
        project: selectedProject,
        status: 'pending',
        timestamp: serverTimestamp()
      });
    } catch (error) {
      console.error(error);
    } finally {
      setIsProcessing(false);
    }
  }

  async function sendTerminalInput() {
    if (!terminalInput.trim() || !selectedTerminal) return;
    try {
      const cmd = terminalInput;
      setTerminalInput('');
      const queueRef = ref(database, `users/${user.uid}/remote_terminals/${selectedSystem}/control`);
      await push(queueRef, {
        type: 'input',
        project: selectedProject,
        terminal_id: selectedTerminal,
        command: cmd,
        status: 'pending',
        timestamp: serverTimestamp()
      });
    } catch (error) {
      console.error(error);
    }
  }

  const activeSystemLabel = systems.find(s => s.value === selectedSystem)?.label || "Loading Systems...";
  const activeProjectLabel = projects.find(p => p.value === selectedProject)?.label || "Select Project";

  if (authLoading) {
    return (
      <LinearGradient colors={['#2A1B3D', '#12121A', '#0A0A0F']} style={[styles.background, {justifyContent: 'center', alignItems: 'center'}]}>
        <ActivityIndicator size="large" color="#0A84FF" />
      </LinearGradient>
    );
  }

  if (!user) {
    return (
      <LinearGradient colors={['#2A1B3D', '#12121A', '#0A0A0F']} style={styles.background}>
        <SafeAreaView style={styles.safeArea}>
          <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={[styles.container, {justifyContent: 'center'}]}>
            <Text style={[styles.title, {textAlign: 'center', marginBottom: 40}]}>PC Link Secure</Text>
            
            <View style={[styles.glassContainer, {padding: 20}]}>
              <GlassBackground intensity={50} tint="dark" />
              <TextInput
                style={[styles.textInput, {height: 50, padding: 10, marginBottom: 16}]}
                placeholder="Email"
                placeholderTextColor="rgba(255,255,255,0.4)"
                value={email}
                onChangeText={setEmail}
                autoCapitalize="none"
              />
              <TextInput
                style={[styles.textInput, {height: 50, padding: 10, marginBottom: 24}]}
                placeholder="Password"
                placeholderTextColor="rgba(255,255,255,0.4)"
                value={password}
                onChangeText={setPassword}
                secureTextEntry
              />
              <TouchableOpacity style={styles.actionButtonWrapper} onPress={handleAuth} activeOpacity={0.7}>
                <GlassBackground intensity={50} tint="light" androidOpacity={0.2} />
                <Text style={styles.actionButtonText}>{isLoginMode ? 'Login' : 'Create Account'}</Text>
              </TouchableOpacity>
              
              <TouchableOpacity onPress={() => setIsLoginMode(!isLoginMode)} style={{marginTop: 20}}>
                <Text style={{color: '#0A84FF', textAlign: 'center'}}>{isLoginMode ? 'Need an account? Sign up' : 'Have an account? Log in'}</Text>
              </TouchableOpacity>
            </View>
          </KeyboardAvoidingView>
        </SafeAreaView>
      </LinearGradient>
    );
  }

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
            
            <View style={[styles.modalHeader, {flexDirection: 'row', gap: 16}]}>
              <TouchableOpacity onPress={() => signOut(auth)} style={styles.closeBtn}>
                <Ionicons name="log-out" size={32} color="#FF3B30" />
              </TouchableOpacity>
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
              {projects.length === 0 ? (
                <Text style={{color: 'rgba(255,255,255,0.5)', marginLeft: 16}}>No projects detected. Open a project in the IDE.</Text>
              ) : (
                projects.map((proj) => (
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
                ))
              )}
            </View>
          </View>
        </Modal>

      <SafeAreaView style={styles.safeArea}>
        <KeyboardAvoidingView 
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={styles.container}
        >
          {/* Header */}
          <View style={styles.header}>
            <TouchableOpacity onPress={() => setIsNavOpen(true)} style={styles.menuIcon}>
              <Ionicons name="ellipsis-horizontal-circle" size={32} color="rgba(255, 255, 255, 0.7)" />
            </TouchableOpacity>
            <View style={styles.headerTitles}>
              <Text style={styles.subtitle}>{activeSystemLabel}</Text>
              <Text style={styles.title}>{activeTab === 'vibe' ? activeProjectLabel : 'Terminals'}</Text>
            </View>
          </View>

          {activeTab === 'vibe' ? (
            <>
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

            {/* Restore Button */}
            <TouchableOpacity 
              style={[styles.actionButtonWrapper, {flex: 1}]}
              onPress={() => {
                if (lastPrompt) {
                  setPromptText(lastPrompt);
                } else {
                  Alert.alert('No History', 'No previous prompt found for this project.');
                }
              }}
              disabled={isProcessing}
              activeOpacity={0.7}
            >
              <GlassBackground intensity={50} tint="dark" />
              <Ionicons name="arrow-undo" size={20} color="#5E5CE6" style={{marginBottom: 4}} />
              <Text style={styles.actionButtonText}>Restore</Text>
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
                  return <LogEntry key={index} log={log} />;
                })
              )}
            </ScrollView>
          </View>
          </>
          ) : (
            <>
              {/* Terminal List Bar */}
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.terminalListScroll}>
                <TouchableOpacity 
                  style={styles.terminalAddBtn}
                  onPress={spawnTerminal}
                  disabled={isProcessing}
                >
                  <Ionicons name="add" size={24} color="#ffffff" />
                </TouchableOpacity>
                {terminals.map(term => (
                  <TouchableOpacity
                    key={term.id}
                    style={[styles.terminalTab, selectedTerminal === term.id && styles.terminalTabActive]}
                    onPress={() => setSelectedTerminal(term.id)}
                  >
                    <Text style={[styles.terminalTabText, selectedTerminal === term.id && styles.terminalTabTextActive]}>
                      TERM-{term.id.substring(0,4).toUpperCase()}
                    </Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>

              {/* Terminal Console View */}
              <View style={[styles.glassContainer, styles.consoleCard, { flex: 1 }]}>
                <GlassBackground intensity={50} tint="dark" />
                <ScrollView 
                  style={styles.consoleScroll}
                  contentContainerStyle={{ paddingBottom: 20 }}
                  ref={terminalScrollRef}
                  onContentSizeChange={() => terminalScrollRef.current?.scrollToEnd({ animated: true })}
                >
                  {terminalLogs.length === 0 ? (
                    <Text style={styles.logTextEmpty}>Awaiting terminal output...</Text>
                  ) : (
                    <Text style={styles.logTextTerminal}>
                      {terminalLogs.map(log => log.text).join('')}
                    </Text>
                  )}
                </ScrollView>
              </View>

              {/* Terminal Input View */}
              <View style={styles.terminalInputRow}>
                <View style={[styles.glassContainer, styles.terminalInputContainer]}>
                  <GlassBackground intensity={50} tint="dark" />
                  <TextInput
                    style={styles.terminalTextInput}
                    placeholder="Type command..."
                    placeholderTextColor="rgba(255, 255, 255, 0.4)"
                    value={terminalInput}
                    onChangeText={setTerminalInput}
                    onSubmitEditing={sendTerminalInput}
                    autoCapitalize="none"
                    autoCorrect={false}
                  />
                </View>
                <TouchableOpacity style={styles.terminalSendBtn} onPress={sendTerminalInput}>
                  <Ionicons name="return-down-back" size={24} color="#ffffff" />
                </TouchableOpacity>
              </View>
            </>
          )}

          {/* Bottom Navigation Tabs */}
          <View style={styles.bottomNav}>
            <TouchableOpacity 
              style={styles.navTab}
              onPress={() => setActiveTab('vibe')}
            >
              <Ionicons name="chatbubbles" size={24} color={activeTab === 'vibe' ? '#0A84FF' : 'rgba(255,255,255,0.5)'} />
              <Text style={[styles.navTabText, activeTab === 'vibe' && styles.navTabTextActive]}>Agent</Text>
            </TouchableOpacity>
            <TouchableOpacity 
              style={styles.navTab}
              onPress={() => setActiveTab('terminals')}
            >
              <Ionicons name="terminal" size={24} color={activeTab === 'terminals' ? '#0A84FF' : 'rgba(255,255,255,0.5)'} />
              <Text style={[styles.navTabText, activeTab === 'terminals' && styles.navTabTextActive]}>Terminals</Text>
            </TouchableOpacity>
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
  logThinking: { color: '#A284F0', fontStyle: 'italic', opacity: 0.8 },
  logResult: { color: '#34C759', backgroundColor: 'rgba(52, 199, 89, 0.05)', padding: 4, borderRadius: 4 },
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
  
  // --- Terminal UI ---
  terminalListScroll: {
    flexGrow: 0,
    marginBottom: 16,
  },
  terminalAddBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(255,255,255,0.1)',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  terminalTab: {
    height: 44,
    paddingHorizontal: 16,
    borderRadius: 22,
    backgroundColor: 'rgba(255,255,255,0.05)',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
  },
  terminalTabActive: {
    backgroundColor: 'rgba(10, 132, 255, 0.2)',
    borderWidth: 1,
    borderColor: '#0A84FF',
  },
  terminalTabText: {
    color: 'rgba(255,255,255,0.5)',
    fontWeight: '600',
    fontSize: 14,
  },
  terminalTabTextActive: {
    color: '#0A84FF',
  },
  logTextTerminal: {
    color: '#E2E8F0',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 12,
    lineHeight: 18,
  },
  terminalInputRow: {
    flexDirection: 'row',
    marginTop: 16,
    marginBottom: 16,
  },
  terminalInputContainer: {
    flex: 1,
    height: 48,
    marginRight: 12,
    justifyContent: 'center',
  },
  terminalTextInput: {
    color: '#ffffff',
    paddingHorizontal: 16,
    height: '100%',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 14,
  },
  terminalSendBtn: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#0A84FF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  bottomNav: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.1)',
  },
  navTab: {
    alignItems: 'center',
  },
  navTabText: {
    color: 'rgba(255,255,255,0.5)',
    fontSize: 12,
    marginTop: 4,
  },
  navTabTextActive: {
    color: '#0A84FF',
  },
});
