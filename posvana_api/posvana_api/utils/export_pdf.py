from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from io import BytesIO
from django.http import HttpResponse
import datetime

def generate_laporan_keuntungan_pdf(data):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = landscape(letter)

    # Judul
    p.setFont("Helvetica-Bold", 16)
    title_text = "Laporan Keuntungan"
    title_width = p.stringWidth(title_text, "Helvetica-Bold", 16)
    p.drawString((width - title_width) / 2, height - 40, title_text)

    # Tanggal cetak di kanan atas
    p.setFont("Helvetica", 10)
    now = datetime.datetime.now()
    tanggal_str = now.strftime("%d %B %Y")  # Misalnya: 16 Juli 2025
    p.drawRightString(width - 40, height - 40, f"Tanggal cetak: {tanggal_str}")

    # Garis bawah judul
    p.setStrokeColor(colors.grey)
    p.line(40, height - 50, width - 40, height - 50)

    # Header tabel
    p.setFont("Helvetica-Bold", 10)
    header_y = height - 70

    col_positions = {
        "nomor": 50,
        "product_name": 100,
        "product_type": 220,
        "capital_price": 320,
        "selling_price": 410,
        "total_terjual": 500,
        "total_pemasukan": 600,
    }

    for col, x in col_positions.items():
        p.drawString(x, header_y, col.replace("_", " ").title())

    # Garis bawah header
    p.line(40, header_y - 5, width - 40, header_y - 5)

    # Isi data
    p.setFont("Helvetica", 9)
    y_position = header_y - 25

    for row in data:
        print(row)

        p.drawString(col_positions["nomor"], y_position, str(row.get("nomor", "")))
        p.drawString(col_positions["product_name"], y_position, str(row.get("product_name", "")))
        p.drawString(col_positions["product_type"], y_position, str(row.get("product_type", "")))
        p.drawString(col_positions["capital_price"], y_position, str(row.get("capital_price", "")))
        p.drawString(col_positions["selling_price"], y_position, str(row.get("selling_price", "")))
        p.drawString(col_positions["total_terjual"], y_position, str(row.get("total_terjual", "")))
        p.drawString(col_positions["total_pemasukan"], y_position, str(row.get("total_pemasukan", "")))

        y_position -= 20
        if y_position < 50:
            p.showPage()
            # Header di setiap halaman
            p.setFont("Helvetica-Bold", 16)
            p.drawString((width - title_width) / 2, height - 40, title_text)
            p.setFont("Helvetica", 10)
            p.drawRightString(width - 40, height - 40, f"Tanggal cetak: {tanggal_str}")
            p.line(40, height - 50, width - 40, height - 50)
            p.setFont("Helvetica-Bold", 10)
            for col, x in col_positions.items():
                p.drawString(x, height - 70, col.replace("_", " ").title())
            p.line(40, height - 75, width - 40, height - 75)
            y_position = height - 95
            p.setFont("Helvetica", 9)

    p.showPage()
    p.save()
    buffer.seek(0)

    return HttpResponse(buffer, content_type="application/pdf", headers={
        "Content-Disposition": "attachment; filename=laporan_keuntungan.pdf"
    })

def generate_laporan_uang_keluar_pdf(data):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = landscape(letter)

    # Judul
    p.setFont("Helvetica-Bold", 16)
    title_text = "Laporan Uang Keluar"
    title_width = p.stringWidth(title_text, "Helvetica-Bold", 16)
    p.drawString((width - title_width) / 2, height - 40, title_text)

    # Tanggal cetak di kanan atas
    p.setFont("Helvetica", 10)
    now = datetime.datetime.now()
    tanggal_str = now.strftime("%d %B %Y")
    p.drawRightString(width - 40, height - 40, f"Tanggal cetak: {tanggal_str}")

    # Garis bawah judul
    p.setStrokeColor(colors.grey)
    p.line(40, height - 50, width - 40, height - 50)

    # Header tabel
    p.setFont("Helvetica-Bold", 11)
    header_y = height - 70

    col_positions = {
        "date": 60,
        "kategori": 200,
        "total_pengeluaran": 450,
    }

    p.drawString(col_positions["date"], header_y, "Tanggal")
    p.drawString(col_positions["kategori"], header_y, "Kategori")
    p.drawString(col_positions["total_pengeluaran"], header_y, "Total Pengeluaran (Rp)")

    # Garis bawah header
    p.line(40, header_y - 5, width - 40, header_y - 5)

    # Isi data
    p.setFont("Helvetica", 10)
    y_position = header_y - 20

    total_semua = 0

    for row in data:
        tanggal = str(row.get("date", ""))
        kategori = str(row.get("kategori", ""))
        pengeluaran = row.get("total_pengeluaran", 0) or 0
        total_semua += pengeluaran

        p.drawString(col_positions["date"], y_position, tanggal)
        p.drawString(col_positions["kategori"], y_position, kategori)
        p.drawRightString(col_positions["total_pengeluaran"] + 80, y_position, f"{pengeluaran:,.0f}")

        # Garis bawah setiap baris
        p.setStrokeColor(colors.lightgrey)
        p.line(40, y_position - 3, width - 40, y_position - 3)

        y_position -= 18

        # Jika penuh, buat halaman baru
        if y_position < 50:
            p.showPage()
            # Header baru di halaman berikutnya
            p.setFont("Helvetica-Bold", 16)
            p.drawString((width - title_width) / 2, height - 40, title_text)
            p.setFont("Helvetica", 10)
            p.drawRightString(width - 40, height - 40, f"Tanggal cetak: {tanggal_str}")
            p.line(40, height - 50, width - 40, height - 50)
            p.setFont("Helvetica-Bold", 11)
            p.drawString(col_positions["date"], height - 70, "Tanggal")
            p.drawString(col_positions["kategori"], height - 70, "Kategori")
            p.drawString(col_positions["total_pengeluaran"], height - 70, "Total Pengeluaran (Rp)")
            p.line(40, height - 75, width - 40, height - 75)
            y_position = height - 95
            p.setFont("Helvetica", 10)

    # Tambahkan total keseluruhan di bawah tabel
    p.setFont("Helvetica-Bold", 11)
    p.drawString(col_positions["kategori"], y_position - 10, "Total Pengeluaran:")
    p.drawRightString(col_positions["total_pengeluaran"] + 80, y_position - 10, f"{total_semua:,.0f}")

    p.showPage()
    p.save()
    buffer.seek(0)

    return HttpResponse(buffer, content_type="application/pdf", headers={
        "Content-Disposition": "attachment; filename=laporan_uang_keluar.pdf"
    })