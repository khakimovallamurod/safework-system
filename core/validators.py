import os
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp']
ALLOWED_DOCUMENT_EXTENSIONS = ['pdf', 'docx', 'doc', 'jpg', 'jpeg', 'png', 'webp']
DANGEROUS_EXTENSIONS = [
    'php', 'phtml', 'php3', 'php4', 'php5', 'php7', 'php8', 'phps',
    'sh', 'bash', 'py', 'pl', 'cgi', 'exe', 'dll', 'so', 'bin',
    'js', 'jsp', 'asp', 'aspx', 'htm', 'html', 'shtml', 'svg'
]

validate_image_extension = FileExtensionValidator(allowed_extensions=ALLOWED_IMAGE_EXTENSIONS)
validate_document_extension = FileExtensionValidator(allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS)


def validate_file_size_10mb(file_obj):
    max_size = 10 * 1024 * 1024  # 10 MB
    if file_obj.size > max_size:
        raise ValidationError("Fayl hajmi 10 MB dan oshmasligi kerak.")


def validate_file_security(file_obj):
    """
    Kengaytirilgan xavfsizlik tekshiruvi:
    Zararli kengaytmalar va ikki tomonlama kengaytmalarni (masalan, test.php.jpg) tekshiradi.
    """
    filename = file_obj.name.lower()
    
    # Ikki tomonlama kengaytma tekshiruvi
    parts = filename.split('.')
    if len(parts) > 1:
        for part in parts[:-1]:
            if part in DANGEROUS_EXTENSIONS:
                raise ValidationError("Xavfli fayl formati aniqlandi. Yuklash rad etildi.")

    ext = os.path.splitext(filename)[1].lstrip('.').lower()
    if ext in DANGEROUS_EXTENSIONS or not ext:
        raise ValidationError("Bunday turdagi fayllarni yuklash xavfsizlik nuqtai nazaridan taqiqlangan.")

    validate_file_size_10mb(file_obj)
