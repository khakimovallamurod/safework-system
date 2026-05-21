from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db.models import FileField

from core.models import StoredMediaFile


class Command(BaseCommand):
    help = "Diskdagi media fayllarni bazaga ko'chiradi va media papkasini tozalaydi."

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-files',
            action='store_true',
            help='Diskdagi fayllarni o\'chirmasdan faqat bazaga yozadi.',
        )

    def handle(self, *args, **options):
        media_root = Path(settings.MEDIA_ROOT)
        imported = 0
        skipped = 0
        from_disk = 0

        for model in apps.get_models():
            file_fields = [
                f for f in model._meta.get_fields()
                if isinstance(f, FileField)
            ]
            if not file_fields:
                continue

            for instance in model.objects.all().iterator():
                for field in file_fields:
                    file_field = getattr(instance, field.name, None)
                    if not file_field or not file_field.name:
                        continue

                    path = file_field.name
                    if StoredMediaFile.objects.filter(path=path).exists():
                        skipped += 1
                        continue

                    disk_path = media_root / path
                    if disk_path.is_file():
                        data = disk_path.read_bytes()
                        content_type = self._guess_type(path)
                        StoredMediaFile.objects.create(
                            path=path,
                            data=data,
                            content_type=content_type,
                            size=len(data),
                        )
                        from_disk += 1
                        imported += 1
                        self.stdout.write(f'  + disk -> db: {path}')
                    elif default_storage.exists(path):
                        with default_storage.open(path, 'rb') as fh:
                            data = fh.read()
                        content_type = self._guess_type(path)
                        StoredMediaFile.objects.create(
                            path=path,
                            data=data,
                            content_type=content_type,
                            size=len(data),
                        )
                        imported += 1
                        self.stdout.write(f'  + storage -> db: {path}')
                    else:
                        self.stdout.write(self.style.WARNING(f'  ! topilmadi: {path}'))

        if media_root.exists() and not options['keep_files']:
            for item in media_root.rglob('*'):
                if item.is_file():
                    item.unlink()
            for item in sorted(media_root.rglob('*'), reverse=True):
                if item.is_dir():
                    try:
                        item.rmdir()
                    except OSError:
                        pass
            self.stdout.write(self.style.SUCCESS('Media papkasi tozalandi.'))

        total = StoredMediaFile.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f'Tayyor: yangi {imported}, avval bor {skipped}, diskdan {from_disk}, '
                f'jami bazada {total} ta fayl.'
            )
        )

    @staticmethod
    def _guess_type(path):
        import mimetypes

        guessed, _ = mimetypes.guess_type(path)
        return guessed or 'application/octet-stream'
