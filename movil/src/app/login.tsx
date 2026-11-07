// Login, as Main.dc.html: the office hero on tinta, then the Django username and password. It asks
// for a device token (POST /api/v1/auth/token) that SecureStore keeps; no cookies.
import { ApiError } from '@compartido/api/client';
import { Redirect } from 'expo-router';
import { useEffect, useRef, useState, type ComponentRef } from 'react';
import { Image, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { LOCK_MS, PROBLEM_TEXT, problemOf } from '@/auth/loginProblems';
import { useSession } from '@/auth/session';
import { Icon } from '@/components/icons';
import { Button, Field, T, errorMessage } from '@/components/ui';
import { colors, radius, shell, space } from '@/theme/tokens';
import HERO from '../../assets/brand/login-oficina-tarde.png';
import LOGO from '../../assets/brand/logo-inverso.png';


export default function Login() {
  const session = useSession();
  const insets = useSafeAreaInsets();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [locked, setLocked] = useState(false);
  const passRef = useRef<ComponentRef<typeof TextInput>>(null);

  useEffect(() => {
    if (!locked) return;
    const timer = setTimeout(() => setLocked(false), LOCK_MS);
    return () => clearTimeout(timer);
  }, [locked]);

  if (session.status === 'dentro' && !sending) return <Redirect href="/" />;

  const problem = problemOf(error);
  const submit = async () => {
    if (sending || locked || !username.trim() || !password) return;
    setSending(true);
    setError(null);
    try {
      await session.login(username, password);
      setPassword('');
    } catch (caught) {
      setError(caught);
      if (caught instanceof ApiError && caught.status === 429) setLocked(true);
    } finally {
      setSending(false);
    }
  };

  return (
    <KeyboardAvoidingView style={styles.screen} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={[styles.content, { paddingTop: insets.top, paddingBottom: insets.bottom + space[6] }]} keyboardShouldPersistTaps="handled">
        <View style={styles.hero}>
          <Image
            source={HERO}
            style={styles.heroImage}
            resizeMode="cover"
            accessibilityLabel="La oficina de 0ff1ce de tarde: la biblioteca con su bibliotecario, la entrada con Operación y la cocina"
          />
          <View style={styles.brand}>
            <Image source={LOGO} style={styles.logo} resizeMode="contain" accessibilityLabel="0ff1ce" />
            <T color={colors.paper}>La oficina de agentes de IA que trabaja tu LinkedIn.</T>
          </View>
        </View>
        <View style={styles.form}>
          <View style={styles.head}>
            <T variant="titulo" accessibilityRole="header">
              Entrar
            </T>
            <T soft>Usa tu usuario y contraseña de Django.</T>
          </View>
          {problem ? (
            <View style={[styles.alert, problem === 'too-many' ? styles.alertWarn : null]} accessibilityRole="alert" accessibilityLiveRegion="assertive">
              <T color={problem === 'too-many' ? colors.ink : colors.alert}>{problem === 'other' ? errorMessage(error) : PROBLEM_TEXT[problem]}</T>
            </View>
          ) : null}
          <Field
            label="Usuario"
            value={username}
            onChangeText={setUsername}
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="username"
            textContentType="username"
            returnKeyType="next"
            onSubmitEditing={() => passRef.current?.focus()}
            testID="login-usuario"
          />
          <View>
            <Field
              ref={passRef}
              label="Contraseña"
              value={password}
              onChangeText={setPassword}
              secureTextEntry={!showPassword}
              autoCapitalize="none"
              autoCorrect={false}
              autoComplete="current-password"
              textContentType="password"
              returnKeyType="go"
              onSubmitEditing={() => void submit()}
              testID="login-clave"
            />
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={showPassword ? 'Ocultar la contraseña' : 'Mostrar la contraseña'}
              onPress={() => setShowPassword((value) => !value)}
              style={styles.eye}
            >
              <Icon name={showPassword ? 'eyeOff' : 'eye'} color={colors.inkSoft} />
            </Pressable>
          </View>
          <Button
            variant="primary"
            block
            disabled={!username.trim() || !password || locked}
            loading={sending}
            loadingLabel="Entrando…"
            onPress={() => void submit()}
            testID="login-entrar"
          >
            Entrar
          </Button>
          <T variant="detalle" soft center>
            Este teléfono queda como un dispositivo de tu cuenta. Puedes cerrarlo desde Ajustes.
          </T>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  content: { flexGrow: 1 },
  hero: { backgroundColor: colors.ink },
  heroImage: { width: '100%', aspectRatio: 384 / 224 },
  brand: { padding: space[4], gap: space[2] },
  logo: { width: 120, height: 34 },
  form: { padding: shell.gutter, gap: space[4] },
  head: { gap: space[1] },
  alert: { padding: space[3], borderWidth: 1, borderColor: colors.alert, borderRadius: radius.sm, backgroundColor: colors.surface },
  alertWarn: { borderColor: colors.postIt, backgroundColor: colors.postIt },
  eye: { position: 'absolute', right: 2, bottom: 2, width: shell.touch, height: shell.touch, alignItems: 'center', justifyContent: 'center' },
});
