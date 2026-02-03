import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import os
import math

st.markdown("""
<style>

button[data-testid="baseButton-primary"],
div.stButton > button {
  background-color: #2E7D6E !important;
  color: #FFFFFF !important;
  border: none !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
}

/* Hover */
button[data-testid="baseButton-primary"]:hover,
div.stButton > button:hover {
  background-color: #25685B !important;
  color: #FFFFFF !important;
}

form button {
  background-color: #2E7D6E !important;
  color: #FFFFFF !important;
  border-radius: 10px !important;
}

div.stDownloadButton > button {
  background-color: #1F5FAA !important; /* azul suave */
  color: #FFFFFF !important;
  border-radius: 10px !important;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
#  FUNCIONES PARA GUARDAR / CARGAR CSV
# ============================================================

def load_csv_list(filename):
    """Carga una lista de diccionarios desde un CSV si existe."""
    if not os.path.exists(filename):
        return []
    df = pd.read_csv(filename)
    records = df.to_dict("records")
    # Convertir NaN a None para evitar problemas con 'nan'
    for r in records:
        for k, v in r.items():
            if isinstance(v, float) and math.isnan(v):
                r[k] = None
    return records


def save_csv_list(filename, records):
    """Guarda una lista de diccionarios en un CSV."""
    if not records:
        # Si está vacío, guardamos un CSV vacío con columnas mínimas
        pd.DataFrame([]).to_csv(filename, index=False)
    else:
        df = pd.DataFrame(records)
        df.to_csv(filename, index=False)


def save_all():
    """Guarda offers, history y notifications en CSV."""
    save_csv_list("offers.csv", st.session_state.offers)
    save_csv_list("history.csv", st.session_state.history)
    save_csv_list("notifications.csv", st.session_state.notifications)


# ============================================================
#  INICIALIZACIÓN DE DATOS
# ============================================================

def init_state():
    if "user" not in st.session_state:
        st.session_state.user = None
        st.session_state.role = None

    # Usuarios de prueba (no se guardan en CSV, son fijos)
    if "users" not in st.session_state:
        st.session_state.users = {
            "producer1": {"password": "producer123", "role": "producer"},
            "buyer1": {"password": "buyer123", "role": "buyer"},
            "buyer2": {"password": "buyer234", "role": "buyer"},
        }

    # Ofertas y contraofertas
    if "offers" not in st.session_state:
        st.session_state.offers = load_csv_list("offers.csv")

    # Historial de movimientos
    if "history" not in st.session_state:
        st.session_state.history = load_csv_list("history.csv")

    # Notificaciones
    if "notifications" not in st.session_state:
        st.session_state.notifications = load_csv_list("notifications.csv")

    # Acciones de compradores sobre ofertas (para ocultarlas en Inicio)
    if "buyer_actions" not in st.session_state:
        st.session_state.buyer_actions = []  # esta parte no se persiste


# ============================================================
#  FUNCIONES AUXILIARES
# ============================================================

def ahora():
    """Devuelve fecha y hora en texto simple."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def generar_id():
    """Genera un id corto para ofertas y contraofertas."""
    return uuid.uuid4().hex[:8]


def registrar_historial(offer_id, actor, accion, detalle):
    st.session_state.history.append(
        {
            "offer_id": offer_id,
            "actor": actor,
            "accion": accion,
            "detalle": detalle,
            "fecha": ahora(),
        }
    )


def enviar_notificacion(usuario, mensaje):
    st.session_state.notifications.append(
        {
            "usuario_destino": usuario,
            "mensaje": mensaje,
            "fecha": ahora(),
        }
    )


def get_oferta_por_id(offer_id):
    for o in st.session_state.offers:
        if o["id"] == offer_id:
            return o
    return None


def marcar_oferta_procesada_por_comprador(buyer, offer_id):
    """Se usa para que el comprador deje de ver esa oferta en Inicio."""
    for a in st.session_state.buyer_actions:
        if a["buyer"] == buyer and a["offer_id"] == offer_id:
            return
    st.session_state.buyer_actions.append(
        {"buyer": buyer, "offer_id": offer_id}
    )


def comprador_ya_proceso_oferta(buyer, offer_id):
    for a in st.session_state.buyer_actions:
        if a["buyer"] == buyer and a["offer_id"] == offer_id:
            return True
    return False


def limpiar_accion_comprador(buyer, offer_id):
    """Permite que el comprador vuelva a ver una oferta en su Inicio
    cuando el productor envía una nueva contraoferta."""
    nueva_lista = []
    for a in st.session_state.buyer_actions:
        if not (a["buyer"] == buyer and a["offer_id"] == offer_id):
            nueva_lista.append(a)
    st.session_state.buyer_actions = nueva_lista


# ============================================================
#  CREACIÓN DE OFERTAS Y CONTRAOFERTAS
# ============================================================

def crear_oferta(productor, toneladas, recoleccion, canastillas, precio, notas):
    nueva_oferta = {
        "id": generar_id(),
        "tipo": "offer",          # oferta normal del productor
        "producer": productor,
        "buyer": None,            # se completa cuando alguien acepta
        "parent_offer_id": None,  # no viene de otra oferta
        "toneladas": toneladas,
        "recoleccion": recoleccion,
        "canastillas": canastillas,
        "precio": precio,
        "notas": notas,
        "status": "open",         # open, accepted, closed, deleted
        "created_at": ahora(),
        "updated_at": ahora(),
    }
    st.session_state.offers.append(nueva_oferta)

    registrar_historial(
        nueva_oferta["id"],
        productor,
        "crear_oferta",
        "El productor creó una oferta inicial.",
    )

    # Notificar a todos los compradores de que hay una nueva oferta
    for username, data in st.session_state.users.items():
        if data["role"] == "buyer":
            enviar_notificacion(
                username,
                f"El productor {productor} publicó una nueva oferta #{nueva_oferta['id']}.",
            )

    save_all()


def crear_contraoferta_comprador(oferta_original, comprador,
                                 toneladas, recoleccion, canastillas,
                                 precio, notas):
    """
    Crea un registro de contraoferta del comprador.
    No cierra la oferta original, solo añade una propuesta.
    """
    contra = {
        "id": generar_id(),
        "tipo": "counter",           # contraoferta del comprador
        "producer": oferta_original["producer"],
        "buyer": comprador,
        "parent_offer_id": oferta_original["id"],
        "toneladas": toneladas,
        "recoleccion": recoleccion,
        "canastillas": canastillas,
        "precio": precio,
        "notas": notas,
        "status": "open",           # open, accepted, rejected, answered, deleted
        "created_at": ahora(),
        "updated_at": ahora(),
    }
    st.session_state.offers.append(contra)

    # La oferta original sigue "open"
    oferta_original["status"] = "open"
    oferta_original["updated_at"] = ahora()

    registrar_historial(
        oferta_original["id"],
        comprador,
        "contraoferta_comprador",
        f"El comprador {comprador} envió una contraoferta.",
    )
    enviar_notificacion(
        oferta_original["producer"],
        f"El comprador {comprador} hizo una contraoferta a tu oferta #{oferta_original['id']}.",
    )

    # El comprador ya tomó una decisión sobre esta oferta → se oculta para él
    marcar_oferta_procesada_por_comprador(comprador, oferta_original["id"])

    save_all()


def contraoferta_vendedor_actualizar(oferta_original, contraoferta,
                                     toneladas, recoleccion, canastillas,
                                     precio, notas):
    """
    El productor responde a la contraoferta del comprador.
    En lugar de crear una oferta nueva, actualiza los datos de la oferta original
    y marca la contraoferta como respondida.
    """
    # Actualizar la oferta original con los nuevos datos
    oferta_original["toneladas"] = toneladas
    oferta_original["recoleccion"] = recoleccion
    oferta_original["canastillas"] = canastillas
    oferta_original["precio"] = precio
    if notas:
        oferta_original["notas"] = notas
    oferta_original["status"] = "open"  # sigue abierta hasta que alguien acepte
    oferta_original["updated_at"] = ahora()

    # Marcar la contraoferta como respondida
    contraoferta["status"] = "answered"
    contraoferta["updated_at"] = ahora()

    registrar_historial(
        oferta_original["id"],
        oferta_original["producer"],
        "contraoferta_vendedor",
        f"El productor envió una contraoferta al comprador {contraoferta['buyer']}.",
    )

    enviar_notificacion(
        contraoferta["buyer"],
        f"El productor {oferta_original['producer']} envió una contraoferta "
        f"sobre la oferta #{oferta_original['id']}.",
    )

    # Permitir que el comprador vuelva a ver la oferta actualizada en su Inicio
    limpiar_accion_comprador(contraoferta["buyer"], oferta_original["id"])

    save_all()


# ============================================================
#  LOGIN
# ============================================================

def login_box():
    st.title("Aguacate Trade")
    st.subheader("Iniciar sesión")

    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        enviar = st.form_submit_button("Entrar")

    if enviar:
        datos = st.session_state.users.get(usuario)
        if datos and datos["password"] == password:
            st.session_state.user = usuario
            st.session_state.role = datos["role"]
            st.rerun()
        else:
            st.error("Credenciales inválidas")


# ============================================================
#  VISTAS
# ============================================================

def vista_inicio_comprador(user):
    st.subheader("Ofertas disponibles")

    # Ocultar ofertas cerradas/eliminadas o ya procesadas por este comprador
    ofertas_disponibles = []
    for o in st.session_state.offers:
        if (
            o.get("tipo") == "offer"
            and o.get("status") not in ["closed", "accepted", "deleted"]
            and not comprador_ya_proceso_oferta(user, o.get("id"))
        ):
            ofertas_disponibles.append(o)

    if not ofertas_disponibles:
        st.info("No hay ofertas disponibles por ahora.")
        return

    for o in ofertas_disponibles:
        with st.container(border=True):
            st.markdown(f"**Oferta #{o['id']} — {o['status']}**")
            st.write(f"Productor: **{o['producer']}**")
            st.write(f"Toneladas: {o['toneladas']}")
            st.write(f"Días de recolección: {o['recoleccion']}")
            st.write(f"Canastillas: {o['canastillas']}")
            st.write(f"Precio: {o['precio']}")
            if o.get("notas"):
                st.write(f"Notas: {o['notas']}")

            c1, c2, c3, c4 = st.columns(4)

            # Me interesa
            if c1.button("Me interesa", key=f"int_{o['id']}_{user}"):
                registrar_historial(
                    o["id"],
                    user,
                    "interes",
                    f"El comprador {user} marcó interés en la oferta.",
                )
                enviar_notificacion(
                    o["producer"],
                    f"El comprador {user} marcó interés en tu oferta #{o['id']}.",
                )
                marcar_oferta_procesada_por_comprador(user, o["id"])
                save_all()
                st.success("Interés registrado.")
                st.rerun()

            # Aceptar oferta directa
            if c2.button("Aceptar", key=f"acc_{o['id']}_{user}"):
                o["status"] = "accepted"
                o["buyer"] = user
                o["updated_at"] = ahora()
                registrar_historial(
                    o["id"],
                    user,
                    "aceptar_oferta",
                    f"El comprador {user} aceptó la oferta.",
                )
                enviar_notificacion(
                    o["producer"],
                    f"El comprador {user} aceptó tu oferta #{o['id']}.",
                )
                marcar_oferta_procesada_por_comprador(user, o["id"])
                save_all()
                st.success("Oferta aceptada. Negocio cerrado.")
                st.rerun()

            # Rechazar oferta
            if c3.button("Rechazar", key=f"rej_offer_{o['id']}_{user}"):
                registrar_historial(
                    o["id"],
                    user,
                    "rechazar_oferta",
                    f"El comprador {user} rechazó la oferta.",
                )
                enviar_notificacion(
                    o["producer"],
                    f"El comprador {user} rechazó tu oferta #{o['id']}.",
                )
                marcar_oferta_procesada_por_comprador(user, o["id"])
                save_all()
                st.warning(
                    "Has rechazado esta oferta. (Sigue disponible para otros compradores)."
                )
                st.rerun()

            # Contraoferta del comprador
            with c4.expander("Contraoferta", expanded=False):
                with st.form(f"form_counter_{o['id']}_{user}"):
                    toneladas = st.number_input(
                        "Toneladas",
                        min_value=0.0,
                        value=float(o["toneladas"]),
                        step=1.0,
                        key=f"ton_c_{o['id']}_{user}",
                    )
                    reco = st.text_input(
                        "Días de recolección",
                        value=o["recoleccion"],
                        key=f"reco_c_{o['id']}_{user}",
                    )
                    can = st.text_input(
                        "Canastillas",
                        value=o["canastillas"],
                        key=f"can_c_{o['id']}_{user}",
                    )
                    precio = st.number_input(
                        "Precio",
                        min_value=0.0,
                        value=float(o["precio"]),
                        step=1.0,
                        key=f"pre_c_{o['id']}_{user}",
                    )
                    notas = st.text_area(
                        "Notas para el productor",
                        value=f"Contraoferta del comprador {user}",
                        key=f"not_c_{o['id']}_{user}",
                    )
                    enviar = st.form_submit_button("Enviar contraoferta")

                    if enviar:
                        crear_contraoferta_comprador(
                            o, user, toneladas, reco, can, precio, notas
                        )
                        st.success("Contraoferta enviada al productor.")
                        st.rerun()


def vista_inicio_productor(user):
    st.subheader("Contraofertas recibidas")

    # Solo contraofertas abiertas del productor
    contraofertas = []
    for c in st.session_state.offers:
        if c.get("tipo") == "counter" and c.get("producer") == user and c.get("status") == "open":
            contraofertas.append(c)

    if not contraofertas:
        st.info("No tienes contraofertas por ahora.")
        return

    for c in contraofertas:
        oferta_original = get_oferta_por_id(c["parent_offer_id"])

        with st.container(border=True):
            st.markdown(f"**Contraoferta #{c['id']}** sobre oferta #{c['parent_offer_id']}")
            st.write(f"Comprador: **{c['buyer']}**")
            st.write(f"Toneladas: {c['toneladas']}")
            st.write(f"Días de recolección: {c['recoleccion']}")
            st.write(f"Canastillas: {c['canastillas']}")
            st.write(f"Precio: {c['precio']}")
            if c.get("notas"):
                st.write(f"Notas: {c['notas']}")

            col1, col2, col3 = st.columns(3)

            # ACEPTAR
            if col1.button("Aceptar", key=f"acc_c_{c['id']}"):
                c["status"] = "accepted"
                c["updated_at"] = ahora()

                if oferta_original:
                    oferta_original["status"] = "closed"
                    oferta_original["buyer"] = c["buyer"]
                    oferta_original["updated_at"] = ahora()

                registrar_historial(
                    c["id"],
                    user,
                    "aceptar_contraoferta",
                    f"El productor aceptó la contraoferta de {c['buyer']}.",
                )
                enviar_notificacion(
                    c["buyer"],
                    f"El productor aceptó tu contraoferta #{c['id']}.",
                )
                save_all()
                st.success("Contraoferta aceptada. Negocio cerrado.")
                st.rerun()

            # RECHAZAR
            if col2.button("Rechazar", key=f"rej_c_{c['id']}"):
                c["status"] = "rejected"
                c["updated_at"] = ahora()
                registrar_historial(
                    c["id"],
                    user,
                    "rechazar_contraoferta",
                    f"El productor rechazó la contraoferta de {c['buyer']}.",
                )
                enviar_notificacion(
                    c["buyer"],
                    f"El productor rechazó tu contraoferta #{c['id']}.",
                )
                save_all()
                st.warning("Contraoferta rechazada.")
                st.rerun()

            # CONTRAOFERTAR (PRODUCTOR) – actualiza la oferta original
            with col3.expander("Contraofertar", expanded=False):
                st.caption(
                    "Enviar nueva propuesta al comprador (se actualiza la oferta original)."
                )
                if oferta_original is None:
                    st.error("No se encontró la oferta original.")
                else:
                    with st.form(f"form_contra_prod_{c['id']}"):
                        toneladas = st.number_input(
                            "Toneladas",
                            min_value=0.0,
                            value=float(oferta_original["toneladas"]),
                            step=1.0,
                            key=f"ton_p_{c['id']}",
                        )
                        reco = st.text_input(
                            "Días de recolección",
                            value=oferta_original["recoleccion"],
                            key=f"reco_p_{c['id']}",
                        )
                        can = st.text_input(
                            "Canastillas",
                            value=oferta_original["canastillas"],
                            key=f"can_p_{c['id']}",
                        )
                        precio = st.number_input(
                            "Precio",
                            min_value=0.0,
                            value=float(oferta_original["precio"]),
                            step=1.0,
                            key=f"pre_p_{c['id']}",
                        )
                        notas = st.text_area(
                            "Notas (opcional)",
                            value=oferta_original.get("notas", ""),
                            key=f"not_p_{c['id']}",
                        )
                        enviar = st.form_submit_button("Enviar contraoferta")

                        if enviar:
                            contraoferta_vendedor_actualizar(
                                oferta_original,
                                c,
                                toneladas,
                                reco,
                                can,
                                precio,
                                notas,
                            )
                            st.success("Se envió una nueva propuesta al comprador.")
                            st.rerun()


def vista_mis_ofertas_productor(user):
    st.subheader("Mis ofertas (productor)")

    mis_ofertas = []
    for o in st.session_state.offers:
        if o.get("producer") == user and o.get("tipo") == "offer":
            mis_ofertas.append(o)

    if not mis_ofertas:
        st.info("Aún no has creado ofertas.")
    else:
        for o in mis_ofertas:
            with st.container(border=True):
                st.markdown(f"**Oferta #{o['id']} — {o['status']}**")
                st.write(f"Comprador final: {o['buyer'] if o['buyer'] else '—'}")
                st.write(f"Toneladas: {o['toneladas']}")
                st.write(f"Días de recolección: {o['recoleccion']}")
                st.write(f"Canastillas: {o['canastillas']}")
                st.write(f"Precio: {o['precio']}")
                st.write(f"Creada: {o['created_at']} · Actualizada: {o['updated_at']}")

                # Eliminar solo si no está cerrada ni aceptada
                if o["status"] not in ["closed", "accepted"]:
                    if st.button("Eliminar oferta", key=f"del_{o['id']}"):
                        o["status"] = "deleted"
                        o["updated_at"] = ahora()
                        registrar_historial(
                            o["id"],
                            user,
                            "eliminar_oferta",
                            "El productor marcó la oferta como eliminada.",
                        )
                        # Notificar a compradores
                        for username, data in st.session_state.users.items():
                            if data["role"] == "buyer":
                                enviar_notificacion(
                                    username,
                                    f"La oferta #{o['id']} fue eliminada por el productor.",
                                )
                        save_all()
                        st.warning(
                            "Oferta eliminada (no visible para compradores)."
                        )
                        st.rerun()

                # Historial + CSV
                with st.expander("Ver historial / Descargar CSV"):
                    registros = [
                        h for h in st.session_state.history if h["offer_id"] == o["id"]
                    ]
                    if registros:
                        df = pd.DataFrame(registros)
                        st.dataframe(df, use_container_width=True)
                        csv = df.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            "Descargar historial en CSV",
                            csv,
                            file_name=f"historial_oferta_{o['id']}.csv",
                            mime="text/csv",
                            key=f"csv_{o['id']}",
                        )
                    else:
                        st.write("Sin registros aún para esta oferta.")

    st.markdown("---")
    st.subheader("Crear nueva oferta")

    with st.form("form_crear_oferta"):
        toneladas = st.number_input("Toneladas", min_value=0.0, step=1.0)
        reco = st.text_input("Días de recolección")
        can = st.text_input("Canastillas")
        precio = st.number_input("Precio", min_value=0.0, step=1.0)
        notas = st.text_area("Notas (opcional)")
        enviar = st.form_submit_button("Publicar oferta")

        if enviar:
            crear_oferta(user, toneladas, reco, can, precio, notas)
            st.success("Oferta creada correctamente.")
            st.rerun()


def vista_mis_ofertas_comprador(user):
    st.subheader("Mis contraofertas enviadas")

    mis_contras = []
    for c in st.session_state.offers:
        if c.get("tipo") == "counter" and c.get("buyer") == user:
            mis_contras.append(c)

    if not mis_contras:
        st.info("No has enviado contraofertas.")
    else:
        for c in mis_contras:
            with st.container(border=True):
                st.markdown(f"**Contraoferta #{c['id']} — {c['status']}**")
                st.write(f"Oferta original: #{c['parent_offer_id']}")
                st.write(f"Productor: {c['producer']}")
                st.write(f"Toneladas: {c['toneladas']}")
                st.write(f"Días de recolección: {c['recoleccion']}")
                st.write(f"Canastillas: {c['canastillas']}")
                st.write(f"Precio: {c['precio']}")
                st.write(f"Creada: {c['created_at']}")

                # Eliminar contraoferta (solo si está abierta)
                if c["status"] == "open":
                    if st.button("Eliminar contraoferta", key=f"del_c_{c['id']}"):
                        c["status"] = "deleted"
                        c["updated_at"] = ahora()
                        registrar_historial(
                            c["parent_offer_id"],
                            user,
                            "eliminar_contraoferta",
                            f"El comprador {user} eliminó su contraoferta.",
                        )
                        enviar_notificacion(
                            c["producer"],
                            f"El comprador {user} eliminó su contraoferta #{c['id']}.",
                        )
                        save_all()
                        st.warning("Contraoferta eliminada.")
                        st.rerun()

                # Historial
                with st.expander("Historial / Descargar CSV"):
                    registros = [
                        h
                        for h in st.session_state.history
                        if h["offer_id"] == c["parent_offer_id"]
                    ]
                    if registros:
                        df = pd.DataFrame(registros)
                        st.dataframe(df, use_container_width=True)
                        csv = df.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            "Descargar historial (oferta + contraofertas)",
                            csv,
                            file_name=f"historial_negocio_{c['parent_offer_id']}.csv",
                            mime="text/csv",
                            key=f"csv_buyer_{c['id']}",
                        )
                    else:
                        st.write("Sin registros aún para este negocio.")

    st.markdown("---")
    st.subheader("Mis ofertas aceptadas (del vendedor)")

    aceptadas = []
    for o in st.session_state.offers:
        if (
            o.get("tipo") == "offer"
            and o.get("buyer") == user
            and o.get("status") in ["closed", "accepted"]
        ):
            aceptadas.append(o)

    if not aceptadas:
        st.info("Todavía no tienes negocios cerrados.")
    else:
        for o in aceptadas:
            with st.container(border=True):
                st.markdown(f"**Oferta #{o['id']} — {o['status']}**")
                st.write(f"Productor: {o['producer']}")
                st.write(f"Toneladas: {o['toneladas']}")
                st.write(f"Días de recolección: {o['recoleccion']}")
                st.write(f"Canastillas: {o['canastillas']}")
                st.write(f"Precio: {o['precio']}")
                st.write(
                    f"Creada: {o['created_at']} · Actualizada: {o['updated_at']}"
                )


def vista_notificaciones(user):
    st.subheader("Notificaciones")

    notis = [n for n in st.session_state.notifications if n["usuario_destino"] == user]
    if not notis:
        st.info("No tienes notificaciones por ahora.")
        return

    # Ordenar de más reciente a más antigua
    notis = sorted(notis, key=lambda x: x["fecha"], reverse=True)

    for n in notis:
        with st.container(border=True):
            st.write(f"**{n['fecha']}** — {n['mensaje']}")


# ============================================================
#  APLICACIÓN PRINCIPAL
# ============================================================

def main():
    init_state()

    if st.session_state.user is None:
        login_box()
        return

    # Barra superior con info de sesión
    st.write(
        f"Sesión: **{st.session_state.user}** · Rol: **{st.session_state.role}**"
    )
    if st.button("Cerrar sesión"):
        st.session_state.user = None
        st.session_state.role = None
        st.rerun()

    # Navegación principal
    pestaña = st.tabs(["Inicio", "Mis ofertas", "Notificaciones"])

    # INICIO
    with pestaña[0]:
        if st.session_state.role == "buyer":
            vista_inicio_comprador(st.session_state.user)
        else:
            vista_inicio_productor(st.session_state.user)

    # MIS OFERTAS
    with pestaña[1]:
        if st.session_state.role == "buyer":
            vista_mis_ofertas_comprador(st.session_state.user)
        else:
            vista_mis_ofertas_productor(st.session_state.user)

    # NOTIFICACIONES
    with pestaña[2]:
        vista_notificaciones(st.session_state.user)


if __name__ == "__main__":
    main()
