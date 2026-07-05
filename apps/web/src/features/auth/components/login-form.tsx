"use client";

import {
  ArrowLeft,
  CheckCircle2,
  Eye,
  EyeOff,
  MailCheck,
  ShieldCheck,
  Stethoscope,
} from "lucide-react";
import { FormEvent, useState } from "react";

import { useAuth } from "@/features/auth/auth-context";

type LoginState = {
  isSubmitting: boolean;
  errorMessage: string | null;
};

type AuthView = "login" | "reset";

export function LoginForm() {
  const { login, resetPassword } = useAuth();
  const [view, setView] = useState<AuthView>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [state, setState] = useState<LoginState>({
    isSubmitting: false,
    errorMessage: null,
  });

  const [resetEmail, setResetEmail] = useState("");
  const [resetState, setResetState] = useState<{
    isSubmitting: boolean;
    errorMessage: string | null;
    isSent: boolean;
  }>({ isSubmitting: false, errorMessage: null, isSent: false });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState({ isSubmitting: true, errorMessage: null });

    try {
      await login(email.trim(), password);
    } catch {
      setState({
        isSubmitting: false,
        errorMessage: "Credenciales inválidas",
      });
    }
  }

  function goToReset() {
    setResetEmail(email.trim());
    setResetState({ isSubmitting: false, errorMessage: null, isSent: false });
    setView("reset");
  }

  function goToLogin() {
    setView("login");
  }

  async function handleResetSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setResetState({ isSubmitting: true, errorMessage: null, isSent: false });

    try {
      await resetPassword(resetEmail.trim());
      setResetState({ isSubmitting: false, errorMessage: null, isSent: true });
    } catch {
      setResetState({
        isSubmitting: false,
        errorMessage: "No pudimos enviar el enlace. Verifica el correo.",
        isSent: false,
      });
    }
  }

  return (
    <main className="auth-screen">
      <div className="auth-layout">
        <LoginBrandHeader />
        <LoginBrandPanel />
        <div className={`auth-card-flip auth-card-flip--${view}`}>
          {view === "login" ? (
            <LoginFormCard
              email={email}
              errorMessage={state.errorMessage}
              isSubmitting={state.isSubmitting}
              onEmailChange={setEmail}
              onForgotPassword={goToReset}
              onPasswordChange={setPassword}
              onSubmit={handleSubmit}
              onTogglePassword={() => setShowPassword((current) => !current)}
              password={password}
              showPassword={showPassword}
            />
          ) : (
            <ResetPasswordCard
              email={resetEmail}
              errorMessage={resetState.errorMessage}
              isSent={resetState.isSent}
              isSubmitting={resetState.isSubmitting}
              onBack={goToLogin}
              onEmailChange={setResetEmail}
              onSubmit={handleResetSubmit}
            />
          )}
        </div>
      </div>
    </main>
  );
}

function LoginBrandHeader() {
  return (
    <div className="auth-brand auth-brand--mobile" aria-label="VetClinic">
      <span className="brand__mark" aria-hidden="true">
        <Stethoscope size={22} />
      </span>
      <span>VetClinic</span>
    </div>
  );
}

function LoginBrandPanel() {
  return (
    <section className="auth-brand-panel" aria-label="Presentación de VetClinic">
      <div className="auth-brand auth-brand--panel">
        <span className="brand__mark brand__mark--large" aria-hidden="true">
          <Stethoscope size={28} />
        </span>
        <span>VetClinic</span>
      </div>

      <div className="auth-brand-panel__copy">
        <p className="eyebrow">Plataforma clínica</p>
        <h1>Operación veterinaria clara, segura y trazable.</h1>
        <p>
          Centraliza pacientes, consultas, agenda, seguimientos e inventario en
          una experiencia pensada para equipos clínicos.
        </p>
      </div>

      <div className="auth-value-list" aria-label="Beneficios de la plataforma">
        <span>
          <CheckCircle2 aria-hidden="true" size={16} />
          Historias clínicas ordenadas
        </span>
        <span>
          <ShieldCheck aria-hidden="true" size={16} />
          Acceso seguro por clínica
        </span>
      </div>
    </section>
  );
}

function LoginFormCard({
  email,
  errorMessage,
  isSubmitting,
  onEmailChange,
  onForgotPassword,
  onPasswordChange,
  onSubmit,
  onTogglePassword,
  password,
  showPassword,
}: {
  email: string;
  errorMessage: string | null;
  isSubmitting: boolean;
  onEmailChange: (value: string) => void;
  onForgotPassword: () => void;
  onPasswordChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onTogglePassword: () => void;
  password: string;
  showPassword: boolean;
}) {
  return (
    <section className="auth-card" aria-labelledby="login-title">
      <div>
        <p className="eyebrow">Acceso clínico</p>
        <h1 id="login-title">Iniciar sesión</h1>
        <p className="auth-card__copy">
          Ingresa con tu usuario autorizado para acceder a la clínica vinculada.
        </p>
      </div>

      <form className="auth-form" onSubmit={onSubmit}>
        <label className="form-field">
          <span>Correo electrónico</span>
          <input
            autoComplete="email"
            onChange={(event) => onEmailChange(event.target.value)}
            required
            type="email"
            value={email}
          />
        </label>

        <label className="form-field">
          <span>Contraseña</span>
          <span className="password-field">
            <input
              autoComplete="current-password"
              onChange={(event) => onPasswordChange(event.target.value)}
              required
              type={showPassword ? "text" : "password"}
              value={password}
            />
            <button
              aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
              className="password-toggle"
              onClick={onTogglePassword}
              type="button"
            >
              {showPassword ? (
                <EyeOff aria-hidden="true" size={19} />
              ) : (
                <Eye aria-hidden="true" size={19} />
              )}
            </button>
          </span>
        </label>

        <div className="auth-support-actions">
          <button
            className="auth-link-button"
            onClick={onForgotPassword}
            type="button"
          >
            ¿Olvidaste tu contraseña?
          </button>
        </div>

        {errorMessage ? <div className="error-state">{errorMessage}</div> : null}

        <button className="primary-button primary-button--full" disabled={isSubmitting} type="submit">
          {isSubmitting ? "Entrando..." : "Entrar"}
        </button>
      </form>
    </section>
  );
}

function ResetPasswordCard({
  email,
  errorMessage,
  isSent,
  isSubmitting,
  onBack,
  onEmailChange,
  onSubmit,
}: {
  email: string;
  errorMessage: string | null;
  isSent: boolean;
  isSubmitting: boolean;
  onBack: () => void;
  onEmailChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className="auth-card" aria-labelledby="reset-title">
      <button
        aria-label="Volver a iniciar sesión"
        className="auth-back-button"
        onClick={onBack}
        type="button"
      >
        <ArrowLeft aria-hidden="true" size={18} />
        <span>Volver</span>
      </button>

      <div>
        <p className="eyebrow">Recuperar acceso</p>
        <h1 id="reset-title">¿Olvidaste tu contraseña?</h1>
        <p className="auth-card__copy">
          Ingresa tu correo y te enviaremos un enlace para restablecerla.
        </p>
      </div>

      {isSent ? (
        <div className="auth-reset-success">
          <span className="auth-reset-success__icon" aria-hidden="true">
            <MailCheck size={26} />
          </span>
          <p>
            Si el correo está registrado, recibirás un enlace de recuperación en
            unos minutos.
          </p>
          <button
            className="primary-button primary-button--full"
            onClick={onBack}
            type="button"
          >
            Volver a iniciar sesión
          </button>
        </div>
      ) : (
        <form className="auth-form" onSubmit={onSubmit}>
          <label className="form-field">
            <span>Correo electrónico</span>
            <input
              autoComplete="email"
              autoFocus
              onChange={(event) => onEmailChange(event.target.value)}
              required
              type="email"
              value={email}
            />
          </label>

          {errorMessage ? (
            <div className="error-state">{errorMessage}</div>
          ) : null}

          <button
            className="primary-button primary-button--full"
            disabled={isSubmitting}
            type="submit"
          >
            {isSubmitting ? "Enviando..." : "Enviar enlace de recuperación"}
          </button>
        </form>
      )}
    </section>
  );
}
