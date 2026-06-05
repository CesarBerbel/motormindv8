from io import BytesIO
import logging
from pathlib import Path
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import PdfSettings, PdfTemplateSettings, PdfTemplateType

logger = logging.getLogger(__name__)


def _text(value):
    if value is None or value == '':
        return '-'
    return str(value)


def _paragraph(value, style):
    safe = escape(_text(value)).replace('\n', '<br/>')
    return Paragraph(safe, style)


def _bool_label(value):
    return 'Sim' if value else 'Não'


def _add_configured_header(story, styles, settings, template):
    if settings.logo:
        try:
            logo_path = Path(settings.logo.path)
            if logo_path.exists():
                img = Image(str(logo_path))
                max_width = 4.5 * cm
                max_height = 2.0 * cm
                ratio = min(max_width / img.imageWidth, max_height / img.imageHeight)
                img.drawWidth = img.imageWidth * ratio
                img.drawHeight = img.imageHeight * ratio
                story.append(img)
                story.append(Spacer(1, 0.15 * cm))
        except Exception:
            logger.exception('Erro ao renderizar logo no PDF.')
    if settings.cabecalho_global:
        story.append(_paragraph(settings.cabecalho_global, styles['SmallMuted']))
        story.append(Spacer(1, 0.15 * cm))
    if template.cabecalho:
        story.append(_paragraph(template.cabecalho, styles['SmallMuted']))
        story.append(Spacer(1, 0.15 * cm))


def _add_configured_footer(story, styles, settings, template):
    footer_blocks = []
    if template.notas_rodape:
        footer_blocks.append(template.notas_rodape)
    if settings.rodape_global:
        footer_blocks.append(settings.rodape_global)
    if not footer_blocks:
        return
    story.append(Spacer(1, 0.35 * cm))
    story.append(Table([['']], colWidths=[17 * cm], rowHeights=[0.01 * cm], style=[
        ('LINEABOVE', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
    ]))
    story.append(Spacer(1, 0.2 * cm))
    for block in footer_blocks:
        story.append(_paragraph(block, styles['SmallMuted']))
        story.append(Spacer(1, 0.12 * cm))


def generate_vehicle_checkin_pdf(checkin):
    pdf_settings = PdfSettings.get_solo()
    template_settings = PdfTemplateSettings.get_for(PdfTemplateType.CHECKIN)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
        title=f'Check-in {checkin.codigo}',
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='SmallMuted', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#666666'), wordWrap='CJK'))
    styles.add(ParagraphStyle(name='SectionTitle', parent=styles['Heading2'], fontSize=13, spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name='Cell', parent=styles['Normal'], fontSize=8.5, leading=10.5, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='CellLabel', parent=styles['Cell'], textColor=colors.HexColor('#374151'), fontName='Helvetica-Bold'))

    story = []
    _add_configured_header(story, styles, pdf_settings, template_settings)

    title = template_settings.titulo or 'Check-in de recepção do veículo'
    story.append(Paragraph(escape(title), styles['Title']))
    story.append(Paragraph(f'{checkin.codigo} - gerado em {timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")}', styles['SmallMuted']))
    story.append(Spacer(1, 0.35 * cm))

    order = checkin.ordem_servico
    vehicle = checkin.veiculo
    customer = checkin.cliente
    vehicle_label = f'{_text(vehicle.placa)} - {_text(vehicle.marca)} {_text(vehicle.modelo)}'
    if vehicle.versao:
        vehicle_label += f' - {_text(vehicle.versao)}'

    data = [
        [_paragraph('Check-in', styles['CellLabel']), _paragraph(checkin.codigo, styles['Cell'])],
        [_paragraph('OS', styles['CellLabel']), _paragraph(order.codigo, styles['Cell'])],
        [_paragraph('Cliente', styles['CellLabel']), _paragraph(customer.nome_razao_social, styles['Cell'])],
        [_paragraph('E-mail', styles['CellLabel']), _paragraph(customer.email, styles['Cell'])],
        [_paragraph('Veículo', styles['CellLabel']), _paragraph(vehicle_label, styles['Cell'])],
        [_paragraph('Chassi', styles['CellLabel']), _paragraph(vehicle.chassi, styles['Cell'])],
        [_paragraph('Data', styles['CellLabel']), _paragraph(timezone.localtime(checkin.data_checkin).strftime('%d/%m/%Y %H:%M'), styles['Cell'])],
        [_paragraph('KM', styles['CellLabel']), _paragraph(checkin.km, styles['Cell'])],
        [_paragraph('Combustível', styles['CellLabel']), _paragraph(checkin.get_nivel_combustivel_display(), styles['Cell'])],
    ]
    table = Table(data, colWidths=[3.3 * cm, 13.7 * cm], repeatRows=0)
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#d1d5db')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f9fafb')),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(table)

    story.append(Paragraph('Itens conferidos', styles['SectionTitle']))
    checked_data = [
        [_paragraph('Item', styles['CellLabel']), _paragraph('Status', styles['CellLabel'])],
        [_paragraph('Estepe', styles['Cell']), _paragraph(_bool_label(checkin.possui_estepe), styles['Cell'])],
        [_paragraph('Macaco', styles['Cell']), _paragraph(_bool_label(checkin.possui_macaco), styles['Cell'])],
        [_paragraph('Chave de roda', styles['Cell']), _paragraph(_bool_label(checkin.possui_chave_roda), styles['Cell'])],
        [_paragraph('Documento do veículo', styles['Cell']), _paragraph(_bool_label(checkin.possui_documento), styles['Cell'])],
    ]
    checked_table = Table(checked_data, colWidths=[8.5 * cm, 8.5 * cm])
    checked_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#d1d5db')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(checked_table)

    text_blocks = [
        ('Objetos deixados no veículo', checkin.objetos_deixados),
        ('Avarias observadas', checkin.avarias_observadas),
        ('Observações gerais', checkin.observacoes),
    ]
    for block_title, value in text_blocks:
        story.append(Paragraph(block_title, styles['SectionTitle']))
        story.append(_paragraph(value or '-', styles['Cell']))

    photos = list(checkin.fotos.all())
    if photos:
        story.append(Paragraph('Fotos anexadas ao check-in', styles['SectionTitle']))
        for photo in photos:
            path = Path(photo.imagem.path)
            if not path.exists():
                continue
            try:
                img = Image(str(path))
                max_width = 15.5 * cm
                max_height = 8.5 * cm
                ratio = min(max_width / img.imageWidth, max_height / img.imageHeight)
                img.drawWidth = img.imageWidth * ratio
                img.drawHeight = img.imageHeight * ratio
                story.append(img)
                story.append(Paragraph(escape(photo.legenda or path.name), styles['SmallMuted']))
                story.append(Spacer(1, 0.25 * cm))
            except Exception:
                logger.exception('Erro ao renderizar foto %s no PDF de check-in.', photo.pk)
                story.append(Paragraph(f'Foto não pôde ser renderizada no PDF: {escape(path.name)}', styles['SmallMuted']))

    if template_settings.mostrar_assinatura_cliente or template_settings.mostrar_assinatura_oficina:
        story.append(Spacer(1, 0.6 * cm))
        if template_settings.mostrar_assinatura_cliente:
            story.append(Paragraph('Assinatura do cliente: ________________________________________________', styles['Normal']))
            story.append(Spacer(1, 0.35 * cm))
        if template_settings.mostrar_assinatura_oficina:
            story.append(Paragraph('Assinatura da recepção: ______________________________________________', styles['Normal']))

    _add_configured_footer(story, styles, pdf_settings, template_settings)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
