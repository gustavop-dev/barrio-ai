// Login, as Main.dc.html: the office hero on tinta, then the Django username and password. It asks
// for a device token (POST /api/v1/auth/token) that SecureStore keeps; no cookies.
//
// After a successful login comes the entrance of MovEntrada (src/entrada). Signed out, the app opens this
// screen over itself (app/(app)/_layout.tsx pushes it as a transparent modal of the root stack), so when the
// session opens the Oficina mounts underneath at once; the pixel door opens, the picture zooms in integer
// steps, and the login fades into the live Oficina before it leaves the stack (goBack). Nothing is reset:
// Expo Router 58 rejects a partial RESET, and the login used to be the first screen of its stack (an opaque
// card with nothing under it to fade into).
//
// The keyboard covers the lower half of a 390×844 screen and the app is drawn edge to edge (the window no
// longer shrinks for it): the form pads itself by the keyboard (KeyboardAvoidingView) and scrolls so the
// fields and «Entrar» sit above it.
import { ApiError } from '@compartido/api/client';
import { Redirect, router, useFocusEffect, useNavigation } from 'expo-router';
import { useCallback, useEffect, useRef, useState, type ComponentRef } from 'react';
import { BackHandler, Image, Keyboard, KeyboardAvoidingView, Pressable, ScrollView, StyleSheet, TextInput, View, useWindowDimensions } from 'react-native';
import Animated, { useAnimatedStyle } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { LOCK_MS, PROBLEM_TEXT, problemOf } from '@/auth/loginProblems';
import { useSession } from '@/auth/session';
import { Icon } from '@/components/icons';
import { Button, Field, T, errorMessage } from '@/components/ui';
import { PixelDoor } from '@/entrada/PixelDoor';
import { useEntrada } from '@/entrada/useEntrada';
import { entrada as entradaMotion, useMotion } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import LOGO from '../../assets/brand/logo-inverso.png';

const HERO_LABEL = 'La oficina de 0ff1ce de tarde: la biblioteca con su bibliotecario, la entrada con Operación y la cocina';

export default function Login() {
  const session = useSession();
  const navigation = useNavigation();
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const { reduced } = useMotion();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [locked, setLocked] = useState(false);
  const [entering, setEntering] = useState(false);
  const passRef = useRef<ComponentRef<typeof TextInput>>(null);
  const scrollRef = useRef<ComponentRef<typeof ScrollView>>(null);
  const opened = useRef(false);
  const keyboardUp = useRef(false);

  /** The login has faded into the Oficina: it leaves the stack. */
  const finish = useCallback(() => {
    if (navigation.canGoBack()) navigation.goBack();
    else router.replace('/');
  }, [navigation]);
  const { door, leaving, shown, running, start } = useEntrada({ reduced, onDone: finish });

  useEffect(() => {
    if (!locked) return;
    const timer = setTimeout(() => setLocked(false), LOCK_MS);
    return () => clearTimeout(timer);
  }, [locked]);

  // Once the session is open, the Oficina is already mounting under the login (the (app) layout renders it
  // as soon as the session says «dentro»): the door opens.
  useEffect(() => {
    if (!entering || session.status !== 'dentro' || opened.current) return;
    opened.current = true;
    start();
  }, [entering, session.status, start]);

  // Android back on the login leaves the app: under it there is only the signed-out app, which opens the login again.
  useFocusEffect(
    useCallback(() => {
      const subscription = BackHandler.addEventListener('hardwareBackPress', () => {
        BackHandler.exitApp();
        return true;
      });
      return () => subscription.remove();
    }, []),
  );

  // With the keyboard up, the end of the form (the fields and «Entrar») scrolls into view above it; again when the
  // padding of the KeyboardAvoidingView has shrunk the scroll view (onLayout below).
  const showForm = useCallback(() => {
    if (keyboardUp.current) scrollRef.current?.scrollToEnd({ animated: !reduced });
  }, [reduced]);
  useEffect(() => {
    const up = Keyboard.addListener('keyboardDidShow', () => {
      keyboardUp.current = true;
      requestAnimationFrame(showForm);
    });
    const down = Keyboard.addListener('keyboardDidHide', () => {
      keyboardUp.current = false;
    });
    return () => {
      up.remove();
      down.remove();
    };
  }, [showForm]);

  const screenStyle = useAnimatedStyle(() => ({ opacity: shown.value }));
  const brandStyle = useAnimatedStyle(() => ({ opacity: 1 - leaving.value }));
  const formStyle = useAnimatedStyle(() => ({ opacity: 1 - leaving.value, transform: [{ translateY: entradaMotion.formDrop * leaving.value }] }));

  if (session.status === 'dentro' && !sending && !entering) return <Redirect href="/" />;

  const problem = problemOf(error);
  const submit = async () => {
    if (sending || locked || entering || !username.trim() || !password) return;
    setSending(true);
    setError(null);
    try {
      await session.login(username, password);
      Keyboard.dismiss();
      scrollRef.current?.scrollTo({ y: 0, animated: !reduced });
      setEntering(true);
    } catch (caught) {
      setError(caught);
      if (caught instanceof ApiError && caught.status === 429) setLocked(true);
      setSending(false);
    }
  };

  return (
    <Animated.View style={[styles.screen, screenStyle]} pointerEvents={running ? 'none' : 'auto'} testID="login">
      <KeyboardAvoidingView style={styles.fill} behavior="padding">
        <ScrollView
          ref={scrollRef}
          onLayout={showForm}
          contentContainerStyle={[styles.content, { paddingTop: insets.top, paddingBottom: insets.bottom + space[6] }]}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.hero}>
            <PixelDoor width={width} door={door} accessibilityLabel={HERO_LABEL} />
            <Animated.View style={[styles.brand, brandStyle]}>
              <Image source={LOGO} style={styles.logo} resizeMode="contain" accessibilityLabel="0ff1ce" />
              <T color={colors.paper}>La oficina de agentes de IA que trabaja tu LinkedIn.</T>
            </Animated.View>
          </View>
          <Animated.View style={[styles.form, formStyle]}>
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
          </Animated.View>
        </ScrollView>
      </KeyboardAvoidingView>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  fill: { flex: 1 },
  content: { flexGrow: 1 },
  hero: { backgroundColor: colors.ink },
  brand: { padding: space[4], gap: space[2] },
  logo: { width: 120, height: 34 },
  form: { padding: shell.gutter, gap: space[4] },
  head: { gap: space[1] },
  alert: { padding: space[3], borderWidth: 1, borderColor: colors.alert, borderRadius: radius.sm, backgroundColor: colors.surface },
  alertWarn: { borderColor: colors.postIt, backgroundColor: colors.postIt },
  eye: { position: 'absolute', right: 2, bottom: 2, width: shell.touch, height: shell.touch, alignItems: 'center', justifyContent: 'center' },
});
