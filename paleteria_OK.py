import streamlit as st
import pandas as pd
from datetime import datetime, date
import datetime as dt
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials

@st.cache_resource
def conectar_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"],
        scope
    )

    client = gspread.authorize(creds)
    return client.open_by_url(
    "https://docs.google.com/spreadsheets/d/1gBNATNp8eYb2m0kPoInfbkuQHmjIVdD21x2LNxnOlbk/edit"

# ============================================
# Archivos y catálogos
# ============================================

CATEGORIAS_PRODUCTOS = [
    "Piramide",
    "Fina",
    "Mini",
    "Gomiloca",
    "Sandwich",
    "Chamoyada",
    "Vaso chico",
    "Vaso grande",
    "Maxi",
    "Congelada",
    "Otros",
]

# ============================================
# Funciones auxiliares
# ============================================


    
def guardar_productos(df: pd.DataFrame):
    df.to_csv(CATALOGO_FILE, index=False)
    
def cargar_productos():
    sheet = conectar_sheets()
    productos = sheet.worksheet("productos")
    data = productos.get_all_records()

    df = pd.DataFrame(data)

    if "stock_minimo" not in df.columns:
        df["stock_minimo"] = 5

    if "costo" not in df.columns:
        df["costo"] = 0.0

    df["precio"] = pd.to_numeric(df["precio"], errors="coerce").fillna(0.0)
    df["costo"] = pd.to_numeric(df["costo"], errors="coerce").fillna(0.0)
    df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0).astype(int)
    df["stock_minimo"] = pd.to_numeric(df["stock_minimo"], errors="coerce").fillna(5).astype(int)

    if "activa" not in df.columns:
        df["activa"] = True

    df["activa"] = df["activa"].astype(bool)

    return df


def cargar_ventas():
    sheet = conectar_sheets()
    ventas = sheet.worksheet("ventas")
    data = ventas.get_all_records()

    df = pd.DataFrame(data)

    if df.empty:
        return pd.DataFrame(
            columns=[
                "fecha",
                "hora",
                "id_producto",
                "producto",
                "categoria",
                "cantidad",
                "precio",
                "total",
                "descuento",
                "metodo_pago",
            ]
        )

    # Tipos numéricos
    for col in ["cantidad", "precio", "total", "descuento"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    return df

def guardar_venta(fila):
    sheet = conectar_sheets()
    ventas = sheet.worksheet("ventas")
    ventas.append_row(fila)

def generar_ticket_pdf(ticket: dict) -> BytesIO:
    """
    Genera un ticket en PDF y devuelve un buffer BytesIO.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Ticket de venta")
    y -= 25

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Fecha: {ticket['fecha']}   Hora: {ticket['hora']}")
    y -= 15
    c.drawString(50, y, f"Método de pago: {ticket['metodo_pago']}")
    y -= 25

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Detalle de productos:")
    y -= 18

    c.setFont("Helvetica", 10)

    for item in ticket["items"]:
        linea = (
            f"- {item['categoria']} - {item['producto']}  "
            f"x{item['cantidad']}  "
            f"${item['precio']:.2f}  "
            f"Subtotal: ${item['subtotal']:.2f}"
        )
        if y < 70:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 10)

        c.drawString(50, y, linea)
        y -= 15

    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, f"Total bruto: ${ticket['total_bruto']:.2f}")
    y -= 15
    c.drawString(50, y, f"Descuento:   -${ticket['descuento']:.2f}")
    y -= 15
    c.drawString(50, y, f"Total a pagar: ${ticket['total']:.2f}")
    y -= 30

    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, y, "¡Gracias por su compra!")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def eliminar_venta_sheet(indice_fila):
    sheet = conectar_sheets()
    ventas = sheet.worksheet("ventas")
    ventas.delete_rows(indice_fila)

# ============================================
# Configuración de página
# ============================================
st.set_page_config(
    
    page_title="Mini POS de Productos",
    page_icon="🧾",
    layout="wide",
)

st.title("🧾 PALETERÍA")

# ============================================
# Cargar datos
# ============================================
df_productos = cargar_productos()
df_ventas = cargar_ventas()

# Inicializar carrito en sesión
if "carrito" not in st.session_state:
    st.session_state["carrito"] = []

# ============================================
# Menú lateral
# ============================================
st.sidebar.title("Menú principal")

rol = st.sidebar.selectbox(
    "Rol de usuario",
    ["Cajero", "Administrador"]
)

if rol == "Administrador":
    opciones_menu = [
        "Registrar venta",
        "Administrar inventario",
        "Reportes",
        "Eliminar venta",

    ]
else:
    opciones_menu = [
        "Registrar venta",
        "Reportes",
        "Eliminar venta",

    ]

seccion = st.sidebar.selectbox(
    "Selecciona una sección",
    opciones_menu
)
def generar_id_producto(df):
    """
    Genera ID_PRODUCTO consecutivo tipo P-001, P-002, ...
    """
    if df.empty or "id_producto" not in df.columns:
        return "P-001"

    ids = (
        df["id_producto"]
        .dropna()
        .astype(str)
        .str.replace("P-", "", regex=False)
    )

    ids = pd.to_numeric(ids, errors="coerce").dropna()

    if ids.empty:
        return "P-001"

    nuevo = int(ids.max()) + 1
    return f"P-{nuevo:03d}"

# ============================================
# Sección: ADMINISTRAR INVENTARIO
# ============================================
if seccion == "Administrar inventario":
    st.subheader("📦 Administrar inventario de productos")
    
    if st.session_state.get("carga_masiva_ok"):
        st.success("✅ Carga masiva y actualizaciones realizadas con éxito.")
        st.session_state["carga_masiva_ok"] = False

    # =====================================
    # 0️⃣ CARGA MASIVA DE PRODUCTOS
    # =====================================
    st.markdown("## 📥 Carga masiva de productos")

    # 1️⃣ Descargar plantilla CSV
    plantilla_df = pd.DataFrame(columns=[
        "id_producto",
        "categoria",
        "nombre",
        "costo",
        "precio",
        "stock",
        "stock_minimo",
        "activa",
    ])

    csv_plantilla = plantilla_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="📄 Descargar plantilla CSV",
        data=csv_plantilla,
        file_name="plantilla_productos.csv",
        mime="text/csv",
    )

    # 2️⃣ Subir archivo CSV
    archivo = st.file_uploader(
        "Sube la plantilla llena",
        type=["csv"]
    )

    # ⬇️ TODO lo siguiente SOLO se ejecuta si hay archivo
    if archivo is not None:

        # 3️⃣ Leer archivo
        df_nuevos = pd.read_csv(
            archivo,
            encoding="latin-1"
        )

        df_nuevos.columns = df_nuevos.columns.str.lower().str.strip()

        # 4️⃣ Validar columnas obligatorias
        columnas_requeridas = ["categoria", "nombre", "costo", "precio", "stock"]
        faltantes = [c for c in columnas_requeridas if c not in df_nuevos.columns]

        if faltantes:
            st.error(f"❌ Faltan columnas obligatorias: {', '.join(faltantes)}")
            st.stop()

        # 5️⃣ Columnas opcionales con valores por defecto
        if "stock_minimo" not in df_nuevos.columns:
            df_nuevos["stock_minimo"] = 5

        if "activa" not in df_nuevos.columns:
            df_nuevos["activa"] = True

        if "id_producto" not in df_nuevos.columns:
            df_nuevos["id_producto"] = ""

        # 6️⃣ Normalizar tipos
        df_nuevos["costo"] = pd.to_numeric(df_nuevos["costo"], errors="coerce").fillna(0.0)
        df_nuevos["precio"] = pd.to_numeric(df_nuevos["precio"], errors="coerce").fillna(0.0)
        df_nuevos["stock"] = pd.to_numeric(df_nuevos["stock"], errors="coerce").fillna(0).astype(int)
        df_nuevos["stock_minimo"] = pd.to_numeric(
            df_nuevos["stock_minimo"], errors="coerce"
        ).fillna(5).astype(int)
        df_nuevos["activa"] = df_nuevos["activa"].astype(bool)

        # 7️⃣ Detectar si el producto ya existe
        def producto_existe(row):
            return (
                (df_productos["nombre"].str.lower() == row["nombre"].lower()) &
                (df_productos["categoria"] == row["categoria"])
            ).any()

        df_nuevos["existe"] = df_nuevos.apply(producto_existe, axis=1)

        # 8️⃣ Vista previa y decisión por fila
        st.markdown("### 👀 Revisión de productos")

        acciones = []

        for i, row in df_nuevos.iterrows():
            st.markdown(f"**{row['categoria']} – {row['nombre']}**")

            if row["existe"]:
                accion = st.selectbox(
                    "Acción",
                    ["Actualizar", "Omitir"],
                    key=f"accion_{i}"
                )
            else:
                accion = st.selectbox(
                    "Acción",
                    ["Agregar", "Omitir"],
                    key=f"accion_{i}"
                )

            acciones.append(accion)

        df_nuevos["accion"] = acciones

        # 9️⃣ Confirmar carga
        if st.button("✅ Confirmar carga masiva"):
            for _, row in df_nuevos.iterrows():

                if row["accion"] == "Omitir":
                    continue

                if row["accion"] == "Agregar":
                    row["id_producto"] = generar_id_producto(df_productos)
                    df_productos = pd.concat(
                        [df_productos, pd.DataFrame([row])],
                        ignore_index=True
                    )

                if row["accion"] == "Actualizar":
                    mask = (
                        (df_productos["nombre"].str.lower() == row["nombre"].lower()) &
                        (df_productos["categoria"] == row["categoria"])
                    )

                    df_productos.loc[
                        mask,
                        ["costo", "precio", "stock", "stock_minimo", "activa"]
                    ] = [
                        row["costo"],
                        row["precio"],
                        row["stock"],
                        row["stock_minimo"],
                        row["activa"],
                    ]

            guardar_productos(df_productos)
            if "carga_masiva_ok" not in st.session_state:
                st.session_state["carga_masiva_ok"] = False
                st.session_state["carga_masiva_file"] = True
                st.rerun()
               
    # ----------------------------------------
    # 1) Agregar nuevo producto
    # ----------------------------------------
    st.markdown("### ➕ Agregar nuevo producto")

    col_id, col_cat, col_nom, col_costo, col_precio, col_stock = st.columns(
    [1, 1.2, 1.5, 1, 1, 1]
    )

    with col_id:
        id_producto = st.text_input(
            "ID del producto",
            placeholder="Ej. P0001"
        )
    with col_cat:
        categoria_nueva = st.selectbox(
            "Categoría",
            CATEGORIAS_PRODUCTOS
        )
       
    with col_nom:
        nombre_nuevo = st.text_input("Nombre del producto")

    with col_costo:
        costo_nuevo = st.number_input(
            "Costo (MXN)",
            min_value=0.0,
            step=0.5,
            format="%.2f"
        )
        
    with col_precio:
        precio_nuevo = st.number_input(
            "Precio (MXN)",
            min_value=0.0,
            step=1.0
        )

    with col_stock:
        stock_nuevo = st.number_input(
            "Stock inicial",
            min_value=0,
            step=1
        )
        
    btn_agregar = st.button("Guardar nuevo producto")

    if btn_agregar:
        id_clean = id_producto.strip()
        nombre_clean = nombre_nuevo.strip()

        if not id_clean:
            st.error("El ID del producto es obligatorio.")
        elif not nombre_clean:
            st.error("Escribe el nombre del producto.")
        elif "id_producto" in df_productos.columns and id_clean in df_productos["id_producto"].astype(str).values:
            st.error("Ese ID_PRODUCTO ya existe. Usa otro.")
        else:
            nueva = {
                "id_producto": id_clean,
                "categoria": categoria_nueva,
                "nombre": nombre_clean,
                "costo": float(costo_nuevo),
                "precio": float(precio_nuevo),
                "stock": int(stock_nuevo),
                "activa": True,
            }

        df_productos = pd.concat(
            [df_productos, pd.DataFrame([nueva])],
            ignore_index=True
        )
        guardar_productos(df_productos)
        st.success("✅ Producto registrado correctamente.")

    st.markdown("---")

    # ----------------------------------------
    # 2) Editar producto existente
    # ----------------------------------------
    st.markdown("### ✏️ Editar producto existente")

    if df_productos.empty:
        st.info("Aún no hay productos registrados.")
    else:
    # Ordenar productos
        df_prod_sorted = df_productos.sort_values(
        ["categoria", "nombre"]
        ).copy()

    # Texto del selector (incluye ID)
    df_prod_sorted["opcion"] = df_prod_sorted.apply(
        lambda r: f"{r['id_producto']} | {r['categoria']} - {r['nombre']}",
        axis=1
    )

    # Selector
    prod_editar_label = st.selectbox(
        "Selecciona un producto para editar",
        df_prod_sorted["opcion"].tolist(),
    )

    # 🔑 Definir fila_sel ANTES del form
    fila_sel = df_prod_sorted[
        df_prod_sorted["opcion"] == prod_editar_label
    ].iloc[0]

    # =========================
    # FORMULARIO
    # =========================
    with st.form("form_editar_producto"):

        # ID (solo lectura)
        st.text_input(
            "ID del producto",
            value=fila_sel["id_producto"],
            disabled=True
        )

        col_cat_e, col_nom_e, col_costo_e, col_precio_e, col_stock_e, col_activa_e = st.columns(
            [1.2, 1.5, 1, 1, 1, 0.8]
        )

        with col_cat_e:
            try:
                idx_cat = CATEGORIAS_PRODUCTOS.index(fila_sel["categoria"])
            except ValueError:
                idx_cat = 0

            nueva_categoria = st.selectbox(
                "Categoría",
                CATEGORIAS_PRODUCTOS,
                index=idx_cat
            )

        with col_nom_e:
            nuevo_nombre = st.text_input(
                "Nombre del producto",
                value=fila_sel["nombre"]
            )

        with col_costo_e:
            nuevo_costo = st.number_input(
                "Costo (MXN)",
                min_value=0.0,
                step=0.5,
                value=float(fila_sel.get("costo", 0.0)),
                format="%.2f"
            )

        with col_precio_e:
            nuevo_precio = st.number_input(
                "Precio (MXN)",
                min_value=0.0,
                step=0.5,
                value=float(fila_sel["precio"]),
                format="%.2f"
            )

        with col_stock_e:
            nuevo_stock = st.number_input(
                "Stock",
                min_value=0,
                step=1,
                value=int(fila_sel["stock"])
            )

        with col_activa_e:
            nueva_activa = st.checkbox(
                "Activo",
                value=bool(fila_sel["activa"])
            )

        # ✅ BOTÓN CORRECTAMENTE DENTRO DEL FORM
        guardar_cambios = st.form_submit_button("Guardar cambios")

    # =========================
    # PROCESAR GUARDADO
    # =========================
    if guardar_cambios:
        mask_target = (
            df_productos["id_producto"] == fila_sel["id_producto"]
        )

        df_productos.loc[
            mask_target,
            ["categoria", "nombre", "costo", "precio", "stock", "activa"],
        ] = [
            nueva_categoria,
            nuevo_nombre.strip(),
            float(nuevo_costo),
            float(nuevo_precio),
            int(nuevo_stock),
            nueva_activa,
        ]

        guardar_productos(df_productos)
        st.success("✅ Cambios guardados correctamente.")

    # ----------------------------------------
    # 3) Productos registrados y resumen de inventario
    # ----------------------------------------
    st.markdown("### 📋 Productos registrados y resumen de inventario")

    if df_productos.empty:
        st.info("No hay productos registrados todavía.")
    else:
        # 1️⃣ Crear DataFrame ordenado
        df_prod_orden = df_productos.sort_values(
            ["categoria", "nombre"]
        ).copy()

        # 2️⃣ Asegurar columnas necesarias
        if "stock_minimo" not in df_prod_orden.columns:
            df_prod_orden["stock_minimo"] = 5

        if "costo" not in df_prod_orden.columns:
            df_prod_orden["costo"] = 0.0

        # 3️⃣ Calcular estado de stock
        def estado_stock(row):
            if row["stock"] <= row["stock_minimo"]:
                return "⚠️ Bajo"
            return "OK"

        df_prod_orden["estado_stock"] = df_prod_orden.apply(
            estado_stock, axis=1
        )

        # 4️⃣ Alerta visual
        productos_bajo_stock = df_prod_orden[
            df_prod_orden["estado_stock"] == "⚠️ Bajo"
        ]

        if not productos_bajo_stock.empty:
            st.warning(
                f"⚠️ {len(productos_bajo_stock)} producto(s) con stock bajo. Revisa el inventario."
            )

        # 5️⃣ Utilidad bruta
        df_prod_orden["utilidad_bruta"] = (
            df_prod_orden["precio"] - df_prod_orden["costo"]
        )

        # 6️⃣ Columnas a mostrar (DESPUÉS de crearlas)
        cols_orden = [
            "id_producto",
            "categoria",
            "nombre",
            "costo",
            "precio",
            "utilidad_bruta",
            "stock",
            "stock_minimo",
            "estado_stock",
            "activa",
        ]

        # 7️⃣ Mostrar tabla
        st.dataframe(
            df_prod_orden[cols_orden],
            use_container_width=True
        )

        # 8️⃣ Descargar CSV
        csv_inv = df_prod_orden[cols_orden].to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "💾 Descargar inventario en CSV",
            csv_inv,
            file_name="inventario_productos.csv",
            mime="text/csv",
        )

        # ============================
        # Totales por categoría
        # ============================
        st.markdown("#### 📊 Total de productos por categoría")

        resumen_cat = (
            df_prod_orden
            .groupby("categoria", as_index=False)["stock"]
            .sum()
            .sort_values("stock", ascending=False)
        )

        total_general = int(resumen_cat["stock"].sum())

        st.table(resumen_cat)

        st.markdown(
            f"**Suma total de artículos en inventario: {total_general}**"
        )

        fig_inv_cat = px.bar(
            resumen_cat,
            x="categoria",
            y="stock",
            title="Total de artículos por categoría",
            labels={
                "categoria": "Categoría",
                "stock": "Número de artículos",
            },
        )
        st.plotly_chart(fig_inv_cat, use_container_width=True)

        # ============================
        # Artículos por producto
        # ============================
        st.markdown(
            "#### 🧃 Artículos por producto (categoría + nombre)"
        )

        stock_sabor = (
            df_prod_orden
            .groupby(
                ["id_producto", "categoria", "nombre"],
                as_index=False
            )["stock"]
            .sum()
        )

        stock_sabor["categoria_producto"] = (
            stock_sabor["categoria"]
            + " - "
            + stock_sabor["nombre"]
        )

        fig_sabor = px.bar(
            stock_sabor,
            x="categoria_producto",
            y="stock",
            title="Número de artículos por producto",
            labels={
                "categoria_producto": "Categoría - Producto",
                "stock": "Número de artículos",
            },
        )
        st.plotly_chart(fig_sabor, use_container_width=True)
# ============================================
# Sección: REGISTRAR VENTA
# ============================================
elif seccion == "Registrar venta":
    st.subheader("🧾 Registrar nueva venta de productos")

    # Sólo productos activos
    productos_activos = df_productos[df_productos["activa"] == True].copy()

    if productos_activos.empty:
        st.warning(
            "No hay productos activos. Ve a **Administrar inventario** para crearlos."
        )
    else:
        # ----------------------------------------
        # Fecha de la venta
        # ----------------------------------------
        st.markdown("#### Fecha de la venta")
        fecha_venta = st.date_input(
            "Selecciona la fecha de la venta",
            value=date.today(),
        )

        # ----------------------------------------
        # Método de pago
        # ----------------------------------------
        metodo_pago = st.selectbox(
            "Método de pago para esta venta",
            ["Efectivo", "Transferencia", "Tarjeta", "Otro"],
        )

        st.markdown("---")
        st.markdown("### 1️⃣ Agregar productos al carrito")

        # ----------------------------------------
        # Selección de categoría
        # ----------------------------------------
        categorias_disponibles = sorted(
            productos_activos["categoria"].unique().tolist()
        )

        categoria_sel = st.radio(
            "Categoría",
            categorias_disponibles,
            horizontal=True,
        )

        productos_cat = (
            productos_activos[
                productos_activos["categoria"] == categoria_sel
            ]
            .sort_values("nombre")
            .copy()
        )

        if productos_cat.empty:
            st.info("No hay productos activos en esta categoría.")
        else:
            st.markdown("#### Elige el producto")

            producto_sel = st.radio(
                "Producto",
                productos_cat["nombre"].tolist(),
                horizontal=True,
            )

            fila = productos_cat[
                productos_cat["nombre"] == producto_sel
            ].iloc[0]

            precio_unit = float(fila["precio"])
            stock_original = int(fila["stock"])
            id_producto = fila["id_producto"]

            # Stock disponible considerando carrito
            cantidad_en_carrito = sum(
                item["cantidad"]
                for item in st.session_state["carrito"]
                if item["id_producto"] == id_producto
            )

            stock_disp = max(stock_original - cantidad_en_carrito, 0)

            col_info, col_cant = st.columns(2)

            with col_info:
                st.info(
                    f"ID: **{id_producto}**  \n"
                    f"Categoría: **{fila['categoria']}**  \n"
                    f"Precio unitario: **${precio_unit:,.2f}**  \n"
                    f"Stock disponible: **{stock_disp}**"
                )

            with col_cant:
                if stock_disp <= 0:
                    st.error("No hay stock disponible.")
                    cantidad = 0
                    btn_agregar = st.button(
                        "Agregar al carrito",
                        disabled=True
                    )
                else:
                    cantidad = st.number_input(
                        "Cantidad a agregar al carrito",
                        min_value=1,
                        max_value=stock_disp,
                        step=1,
                        format="%d",
                    )
                    btn_agregar = st.button("Agregar al carrito")

            if btn_agregar and cantidad > 0:
                st.session_state["carrito"].append(
                    {
                        "id_producto": id_producto,
                        "categoria": categoria_sel,
                        "producto": producto_sel,
                        "cantidad": int(cantidad),
                        "precio": precio_unit,
                    }
                )
                st.success(
                    f"Se agregaron {cantidad} x {producto_sel} al carrito."
                )

        # ----------------------------------------
        # Carrito actual
        # ----------------------------------------
        st.markdown("---")
        st.markdown("### 2️⃣ Carrito actual")

        if not st.session_state["carrito"]:
            st.info("El carrito está vacío.")
        else:
            df_carrito = pd.DataFrame(st.session_state["carrito"])
            df_carrito["subtotal"] = (
                df_carrito["cantidad"] * df_carrito["precio"]
            )

            df_carrito_mostrar = df_carrito[
                [
                    "id_producto",
                    "categoria",
                    "producto",
                    "cantidad",
                    "precio",
                    "subtotal",
                ]
            ]

            st.dataframe(
                df_carrito_mostrar,
                use_container_width=True
            )

            total_bruto = float(df_carrito["subtotal"].sum())

            # ----------------------------------------
            # Descuento
            # ----------------------------------------
            st.markdown("#### 3️⃣ Descuento y total del ticket")

            descuento = st.number_input(
                "Descuento total del ticket (MXN)",
                min_value=0.0,
                max_value=total_bruto,
                step=1.0,
                value=0.0,
            )

            total_final = total_bruto - descuento

            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.metric("Total bruto", f"${total_bruto:,.2f}")
            with col_t2:
                st.metric(
                    "Total después de descuento",
                    f"${total_final:,.2f}"
                )

            # ----------------------------------------
            # Confirmar venta
            # ----------------------------------------
            st.markdown("---")
            st.markdown("### 4️⃣ Confirmar y registrar venta")

            btn_registrar = st.button(
                "Registrar venta y generar ticket"
            )

            if btn_registrar:
                df_prod_local = df_productos.copy()
                error_stock = False

                for _, item in df_carrito.iterrows():
                    mask = (
                        df_prod_local["id_producto"]
                        == item["id_producto"]
                    )

                    if not mask.any():
                        st.error(
                            f"No se encontró el producto "
                            f"ID {item['id_producto']}."
                        )
                        error_stock = True
                        break

                    idx = df_prod_local.index[mask][0]
                    stock_actual = int(
                        df_prod_local.loc[idx, "stock"]
                    )

                    if item["cantidad"] > stock_actual:
                        st.error(
                            f"Stock insuficiente para "
                            f"{item['producto']}."
                        )
                        error_stock = True
                        break

                if not error_stock:
                    # Descontar stock
                    for _, item in df_carrito.iterrows():
                        mask = (
                            df_prod_local["id_producto"]
                            == item["id_producto"]
                        )
                        idx = df_prod_local.index[mask][0]
                        df_prod_local.loc[idx, "stock"] -= int(
                            item["cantidad"]
                        )

                    guardar_productos(df_prod_local)

                    # Registrar ventas
                    ahora = datetime.now()
                    hora_str = ahora.strftime("%H:%M:%S")
                    fecha_str = fecha_venta.isoformat()

                    filas = []
                    for _, item in df_carrito.iterrows():
                        proporcion = (
                            item["subtotal"] / total_bruto
                            if total_bruto > 0
                            else 0
                        )
                        desc_item = round(
                            descuento * proporcion, 2
                        )

                        filas.append(
                            {
                                "fecha": fecha_str,
                                "hora": hora_str,
                                "id_producto": item["id_producto"],
                                "producto": item["producto"],
                                "categoria": item["categoria"],
                                "cantidad": int(item["cantidad"]),
                                "precio": float(item["precio"]),
                                "total": float(item["subtotal"]) - desc_item,
                                "descuento": desc_item,
                                "metodo_pago": metodo_pago,
                            }
                        )

                    df_ventas = pd.concat(
                        [df_ventas, pd.DataFrame(filas)],
                        ignore_index=True
                    )
                    guardar_ventas(df_ventas)

                    ticket_data = {
                        "fecha": fecha_str,
                        "hora": hora_str,
                        "metodo_pago": metodo_pago,
                        "total_bruto": total_bruto,
                        "descuento": descuento,
                        "total": total_final,
                        "items": df_carrito_mostrar.to_dict(
                            orient="records"
                        ),
                    }

                    buffer_pdf = generar_ticket_pdf(ticket_data)

                    st.success(
                        f"Venta registrada por ${total_final:,.2f}"
                    )
                    st.balloons()

                    st.download_button(
                        "🧾 Descargar ticket en PDF",
                        buffer_pdf,
                        file_name=(
                            f"ticket_{ahora.strftime('%Y%m%d_%H%M%S')}.pdf"
                        ),
                        mime="application/pdf",
                    )

                    st.session_state["carrito"] = []
# ============================================
# Sección: REPORTES
# ============================================
elif seccion == "Reportes":
    st.subheader("📊 Reportes de ventas")

    df_ventas = cargar_ventas()

    if df_ventas.empty:
        st.info("Aún no hay ventas registradas.")
    else:
        tab_corte, tab_rango = st.tabs(
            ["Corte del día", "Análisis por rango"]
        )

        # =========================
        # 1) CORTE DEL DÍA
        # =========================
        with tab_corte:
            st.markdown("### 🧾 Corte del día")

            fecha_sel = st.date_input(
                "Selecciona la fecha del corte",
                dt.date.today()
            )
            fecha_sel_str = fecha_sel.isoformat()

            df_dia = df_ventas[
                df_ventas["fecha"] == fecha_sel_str
            ]

            if df_dia.empty:
                st.warning(
                    "No hay ventas registradas para esta fecha."
                )
            else:
                st.markdown(
                    f"#### Resumen del {fecha_sel_str}"
                )

                # Totales por método de pago
                resumen_metodo = (
                    df_dia
                    .groupby("metodo_pago", as_index=False)["total"]
                    .sum()
                    .sort_values("total", ascending=False)
                )

                resumen_metodo["total"] = (
                    resumen_metodo["total"].round(2)
                )

                st.markdown("**Totales por método de pago**")
                st.table(resumen_metodo)

                # Detalle del día (incluye ID_PRODUCTO)
                columnas_orden = [
                    "fecha",
                    "hora",
                    "id_producto",
                    "categoria",
                    "producto",
                    "cantidad",
                    "precio",
                    "total",
                    "descuento",
                    "metodo_pago",
                ]
                columnas_orden = [
                    c for c in columnas_orden
                    if c in df_dia.columns
                ]

                st.dataframe(
                    df_dia[columnas_orden],
                    use_container_width=True
                )

                csv_corte = (
                    df_dia[columnas_orden]
                    .to_csv(index=False)
                    .encode("utf-8")
                )

                st.download_button(
                    label="💾 Descargar corte en CSV",
                    data=csv_corte,
                    file_name=f"corte_{fecha_sel_str}.csv",
                    mime="text/csv",
                )

        # =========================
        # 2) ANÁLISIS POR RANGO
        # =========================
        with tab_rango:
            st.markdown("### 📈 Análisis por rango de fechas")

            col_f1, col_f2 = st.columns(2)
            with col_f1:
                fecha_ini = st.date_input(
                    "Fecha inicial",
                    dt.date.today().replace(day=1)
                )
            with col_f2:
                fecha_fin = st.date_input(
                    "Fecha final",
                    dt.date.today()
                )

            if fecha_ini > fecha_fin:
                st.error(
                    "La fecha inicial no puede ser mayor que la final."
                )
            else:
                f_ini = fecha_ini.isoformat()
                f_fin = fecha_fin.isoformat()

                df_rango = df_ventas[
                    (df_ventas["fecha"] >= f_ini) &
                    (df_ventas["fecha"] <= f_fin)
                ].copy()

                if df_rango.empty:
                    st.warning(
                        "No hay ventas en el rango seleccionado."
                    )
                else:
                    st.markdown(
                        f"Ventas del **{f_ini}** al **{f_fin}**"
                    )

                    # Columna combinada
                    df_rango["categoria_producto"] = (
                        df_rango["categoria"]
                        + " - "
                        + df_rango["producto"]
                    )

                    # 2.1 Cantidad vendida
                    st.markdown(
                        "#### 🟦 Cantidad de artículos vendidos"
                    )
                    ventas_cant = (
                        df_rango
                        .groupby(
                            ["id_producto", "categoria_producto"],
                            as_index=False
                        )["cantidad"]
                        .sum()
                        .sort_values("cantidad", ascending=False)
                    )

                    fig_cant = px.bar(
                        ventas_cant,
                        x="categoria_producto",
                        y="cantidad",
                        title="Cantidad vendida por producto",
                        labels={
                            "categoria_producto": "Producto",
                            "cantidad": "Unidades",
                        },
                    )
                    st.plotly_chart(
                        fig_cant,
                        use_container_width=True
                    )

                    # 2.2 Ventas en $
                    st.markdown(
                        "#### 🟩 Ventas en $ por producto"
                    )
                    ventas_total = (
                        df_rango
                        .groupby(
                            ["id_producto", "categoria_producto"],
                            as_index=False
                        )["total"]
                        .sum()
                        .sort_values("total", ascending=False)
                    )

                    fig_total = px.bar(
                        ventas_total,
                        x="categoria_producto",
                        y="total",
                        title="Ventas totales por producto",
                        labels={
                            "categoria_producto": "Producto",
                            "total": "Ventas ($)",
                        },
                    )
                    st.plotly_chart(
                        fig_total,
                        use_container_width=True
                    )

                    # 2.3 Método de pago
                    st.markdown(
                        "#### 🟣 Distribución por método de pago"
                    )
                    ventas_pago = (
                        df_rango
                        .groupby(
                            "metodo_pago",
                            as_index=False
                        )["total"]
                        .sum()
                    )

                    fig_pago = px.pie(
                        ventas_pago,
                        names="metodo_pago",
                        values="total",
                        title="Método de pago",
                    )
                    st.plotly_chart(
                        fig_pago,
                        use_container_width=True
                    )

                    # 2.4 Ventas por categoría
                    st.markdown(
                        "#### 🟠 Ventas por categoría"
                    )
                    ventas_cat = (
                        df_rango
                        .groupby(
                            "categoria",
                            as_index=False
                        )["total"]
                        .sum()
                        .sort_values("total", ascending=False)
                    )

                    fig_cat = px.bar(
                        ventas_cat,
                        x="categoria",
                        y="total",
                        title="Ventas por categoría",
                        labels={
                            "categoria": "Categoría",
                            "total": "Ventas ($)",
                        },
                    )
                    st.plotly_chart(
                        fig_cat,
                        use_container_width=True
                    )

                    # 2.5 Ventas por día ($)
                    st.markdown(
                        "#### 📅 Total vendido por día ($)"
                    )
                    ventas_dia_total = (
                        df_rango
                        .groupby(
                            "fecha",
                            as_index=False
                        )["total"]
                        .sum()
                        .sort_values("fecha")
                    )

                    fig_dia_total = px.bar(
                        ventas_dia_total,
                        x="fecha",
                        y="total",
                        title="Ventas por día",
                        labels={
                            "fecha": "Fecha",
                            "total": "Ventas ($)",
                        },
                    )
                    st.plotly_chart(
                        fig_dia_total,
                        use_container_width=True
                    )

                    # 2.6 Cantidad por día
                    st.markdown(
                        "#### 📦 Cantidad de productos vendidos por día"
                    )
                    ventas_dia_cant = (
                        df_rango
                        .groupby(
                            "fecha",
                            as_index=False
                        )["cantidad"]
                        .sum()
                        .sort_values("fecha")
                    )

                    fig_dia_cant = px.bar(
                        ventas_dia_cant,
                        x="fecha",
                        y="cantidad",
                        title="Unidades vendidas por día",
                        labels={
                            "fecha": "Fecha",
                            "cantidad": "Unidades",
                        },
                    )
                    st.plotly_chart(
                        fig_dia_cant,
                        use_container_width=True
                    )
###---NUEVA SECCION--- ####
elif seccion == "Eliminar venta":
    st.subheader("🗑️ Eliminar venta registrada")

    df_ventas = cargar_ventas()

    if df_ventas.empty:
        st.info("No hay ventas registradas.")
    else:
        df_ventas_reset = df_ventas.reset_index()

        st.dataframe(df_ventas_reset, use_container_width=True)

        opcion = st.selectbox(
            "Selecciona la venta a eliminar",
            df_ventas_reset.index,
            format_func=lambda x: (
                f"{df_ventas_reset.loc[x,'fecha']} | "
                f"{df_ventas_reset.loc[x,'producto']} | "
                f"${df_ventas_reset.loc[x,'total']}"
            )
        )

        if st.button("Eliminar venta seleccionada"):
            fila_sheet = int(opcion) + 2  # encabezado + base 1
            eliminar_venta_sheet(fila_sheet)

            st.success("Venta eliminada correctamente.")
            st.rerun()


