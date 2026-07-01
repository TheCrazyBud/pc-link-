import re

with open('App.js', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add Auth imports
content = re.sub(
    r"import \{ initializeApp \} from 'firebase/app';",
    r"import { initializeApp } from 'firebase/app';\nimport { getAuth, signInWithEmailAndPassword, createUserWithEmailAndPassword, onAuthStateChanged, signOut } from 'firebase/auth';",
    content
)

content = re.sub(
    r"const database = getDatabase\(app\);",
    r"const database = getDatabase(app);\nconst auth = getAuth(app);",
    content
)

# 2. Add User state and Auth UI to Index
index_start = r"export default function Index\(\) \{"
new_index_start = '''export default function Index() {
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
'''
content = re.sub(index_start, new_index_start, content)

# 3. Add Login Screen UI if !user
return_start = r"  return \(\n    <LinearGradient colors=\{\['#2A1B3D', '#12121A', '#0A0A0F'\]\} style=\{styles\.background\}>\n"
new_return_start = '''  if (authLoading) {
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
'''
content = re.sub(return_start, new_return_start, content)

# 4. Scope DB Paths
path_replacements = [
    (r"ref\(database, 'systems'\)", r"ref(database, `users/${user.uid}/systems`)"),
    (r"ref\(database, `systems/\$\{selectedSystem\}/projects`\)", r"ref(database, `users/${user.uid}/systems/${selectedSystem}/projects`)"),
    (r"ref\(database, `live_logs/\$\{selectedSystem\}/\$\{selectedProject\}`\)", r"ref(database, `users/${user.uid}/live_logs/${selectedSystem}/${selectedProject}`)"),
    (r"ref\(database, `remote_terminals/\$\{selectedSystem\}/\$\{selectedProject\}/active`\)", r"ref(database, `users/${user.uid}/remote_terminals/${selectedSystem}/${selectedProject}/active`)"),
    (r"ref\(database, `remote_terminals/\$\{selectedSystem\}/\$\{selectedProject\}/\$\{selectedTerminal\}/logs`\)", r"ref(database, `users/${user.uid}/remote_terminals/${selectedSystem}/${selectedProject}/${selectedTerminal}/logs`)"),
    (r"ref\(database, `pending_prompts/\$\{selectedSystem\}`\)", r"ref(database, `users/${user.uid}/pending_prompts/${selectedSystem}`)"),
    (r"ref\(database, `remote_terminals/\$\{selectedSystem\}/control`\)", r"ref(database, `users/${user.uid}/remote_terminals/${selectedSystem}/control`)")
]

for old, new in path_replacements:
    content = re.sub(old, new, content)

# Add logout button to modal header
modal_header_old = r'<View style=\{styles\.modalHeader\}>\n              <TouchableOpacity onPress=\{\(\) => setIsNavOpen\(false\)\} style=\{styles\.closeBtn\}>\n                <Ionicons name="close-circle" size=\{32\} color="#ffffff" />\n              </TouchableOpacity>\n            </View>'
modal_header_new = '''<View style={[styles.modalHeader, {flexDirection: 'row', gap: 16}]}>
              <TouchableOpacity onPress={() => signOut(auth)} style={styles.closeBtn}>
                <Ionicons name="log-out" size={32} color="#FF3B30" />
              </TouchableOpacity>
              <TouchableOpacity onPress={() => setIsNavOpen(false)} style={styles.closeBtn}>
                <Ionicons name="close-circle" size={32} color="#ffffff" />
              </TouchableOpacity>
            </View>'''
content = re.sub(modal_header_old, modal_header_new, content)

with open('App.js', 'w', encoding='utf-8') as f:
    f.write(content)
print("App.js patched successfully.")
