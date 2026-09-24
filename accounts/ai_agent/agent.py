import os
import json
import logging
import urllib.request as urlrequest
import urllib.error as urlerror
from django.conf import settings
from .tools import SoplineDataTools, GEMINI_TOOLS_DECLARATION

logger = logging.getLogger(__name__)


class SoplineAIAgent:
    """
    Sopline System uchun avtonom AI Agent.
    Gemini 3.8-flash (va uning muqobil modellari) asosida Function Calling (Tools) orqali ishlaydi.
    """

    def __init__(self, user, role_context):
        self.user = user
        self.role_context = role_context
        self.tools = SoplineDataTools(user, role_context)
        # API kalitni to'g'ridan-to'g'ri os.getenv yoki settings orqali aniq olish
        raw_key = os.getenv('GEMINI_API_KEY') or getattr(settings, 'GEMINI_API_KEY', '') or ''
        self.api_key = raw_key.strip().strip('"').strip("'")
        
        # Google Generative Language API da mavjud bo'lgan modellar
        primary_model = os.getenv('GEMINI_MODEL') or getattr(settings, 'GEMINI_MODEL', 'gemini-3.8-flash') or 'gemini-3.8-flash'
        primary_model = primary_model.strip().strip('"').strip("'")
        all_candidates = [primary_model, 'gemini-3.8-flash', 'gemini-3.6-flash', 'gemini-2.5-flash', 'gemini-flash-latest', 'gemini-pro-latest']
        self.models_to_try = []
        for m in all_candidates:
            if m and m not in self.models_to_try:
                self.models_to_try.append(m)

    def _get_system_instruction(self):
        profile = getattr(self.user, 'profile', None)
        role_title = profile.get_role_display() if profile else ("Super Admin" if self.user.is_superuser else "Foydalanuvchi")
        org_name = profile.organization_name if profile else "Sopline Tizimi"
        dept_name = profile.department.name if profile and profile.department else "Barcha boshqarmalar"
        sec_name = profile.section.name if profile and profile.section else "Barcha bo'limlar"

        instruction = f"""
Siz "Sopline System" — zamonaviy mehnat muhofazasi va xavfsizlik boshqaruv tizimining rasmiy AI Agentisiz.
Hozirgi foydalanuvchi ma'lumotlari:
- Ismi: {self.user.get_full_name() or self.user.username}
- Tizimdagi roli: {role_title}
- Tashkilot: {org_name}
- Boshqarma: {dept_name}
- Bo'lim: {sec_name}
- Hudud/Viloyat: {profile.region.name if profile and profile.region else "Barcha hududlar"}

QAT'IY TALABLAR (BU QOIDALARGA QAT'IY AMAL QILING):
1. MATNDA HECH QANDAY SARLAVHA YOZMANG:
   - Javobingizda hech qachon sarlavha (masalan: '#', '##', '###', '---', 'Mavzu:', 'Sarlavha:' yoki alohida sarlavha qatorlari) ishlatmang.
   - Matnni to'g'ridan-to'g'ri birinchi gapdanoq mazmunga kirishib, oddiy tushunarli xatboshilar yoki oddiy punktlar (•) shaklida bayon qiling.
2. SAYT TAHLILI, HISOBOTLAR VA KELIB-KETISH FAOLLIGI:
   - Foydalanuvchi "Kim qachon kirdi?", "Necha marta kirdi?", "Saytda qancha vaqt ishladi?", "Faollik qanday?" deb so'rasa, albatta `get_system_usage_and_activity` vositasidan foydalanib aniq sanalar, soatlar va sonlar bilan faktik javob bering.
   - Foydalanuvchi saytni analiz qilishni, umumiy hisobot berishni yoki yacheyka holatini tahlil qilishni so'rasa, `get_safety_analysis_report` vositasidan foydalanib xulosaviy tahlil taqdim eting.
3. ROL VA YACHEYKA CHEKLOVLARI:
   - Foydalanuvchi faqat o'z yacheykasiga doir ma'lumotlarni ko'radi:
     • Inspektor / Nazoratchi bo'lsa: o'z hududi (viloyati) bo'yicha;
     • Tashkilot rahbari (Direktor) bo'lsa: butun korxona/zavod bo'yicha;
     • Boshqarma boshlig'i bo'lsa: o'z boshqarmasi bo'yicha;
     • Bo'lim boshlig'i bo'lsa: qat'iy ravishda faqat o'z bo'limi bo'yicha;
     • Xodim bo'lsa: faqat o'z ma'lumotlari bo'yicha.
4. RAG VA HUJJATLAR QIDIRUVI:
   - Mehnat muhofazasi qoidalari, qonunlar, standartlar haqidagi savollar uchun `search_safety_documents` dan foydalaning.
5. Javoblaringiz to'liq o'zbek tilida, xolis, aniq va professional bo'lsin.
"""
        return instruction.strip()

    @staticmethod
    def _clean_text(text):
        if not text:
            return ""
        import re
        # Gorizontal ajratuvchi chiziqlarni tozalash (---, ***, ___)
        text = re.sub(r'^\s*[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
        # Markdown sarlavha belgilarini (#, ##, ###, ####) qator boshidan olib tashlash
        text = re.sub(r'^\s*#{1,6}\s*', '', text, flags=re.MULTILINE)
        # Alohida sarlavha prefikslarini olib tashlash (masalan: "Sarlavha:", "Mavzu:")
        text = re.sub(r'^(?:sarlavha|mavzu|title|javob)\s*:\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
        # Ortiqcha bo'sh qatorlarni qisqartirish
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _execute_tool(self, function_name, arguments):
        """
        Gemini tomonidan chaqirilgan tool nomiga qarab mos funksiyani bajaradi.
        """
        tool_map = {
            "search_safety_documents": self.tools.search_safety_documents,
            "get_user_profile_and_permissions": self.tools.get_user_profile_and_permissions,
            "get_organization_and_structure_info": self.tools.get_organization_and_structure_info,
            "get_workers_summary": self.tools.get_workers_summary,
            "get_violations_and_compliance": self.tools.get_violations_and_compliance,
            "get_explanation_letters": self.tools.get_explanation_letters,
            "get_ppe_safety_equipment_info": self.tools.get_ppe_safety_equipment_info,
            "get_ppe_types_catalog": self.tools.get_ppe_types_catalog,
            "get_guidelines_status": self.tools.get_guidelines_status,
            "get_mandatory_guidelines_details": self.tools.get_mandatory_guidelines_details,
            "get_practices_and_assessments": self.tools.get_practices_and_assessments,
            "get_practice_test_results": self.tools.get_practice_test_results,
            "get_department_assessments": self.tools.get_department_assessments,
            "get_medical_and_certificates_info": self.tools.get_medical_and_certificates_info,
            "get_employee_certificates": self.tools.get_employee_certificates,
            "get_professions_and_standards": self.tools.get_professions_and_standards,
            "get_section_messages_and_tasks": self.tools.get_section_messages_and_tasks,
            "get_system_usage_and_activity": self.tools.get_system_usage_and_activity,
            "get_safety_analysis_report": self.tools.get_safety_analysis_report,
        }

        func = tool_map.get(function_name)
        if not func:
            return {"error": f"Noma'lum funksiya: {function_name}"}

        try:
            res = func(**(arguments or {}))
            return res
        except Exception as e:
            logger.exception(f"Tool execution error: {function_name}")
            return {"error": f"Xatolik: {str(e)}"}

    def _call_gemini_api(self, model, contents, with_tools=True):
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"

        payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": self._get_system_instruction()}]
            },
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1000
            }
        }

        if with_tools:
            payload["tools"] = [{
                "functionDeclarations": GEMINI_TOOLS_DECLARATION
            }]

        req = urlrequest.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urlrequest.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def answer_question(self, question, chat_history=None):
        """
        Foydalanuvchi savoliga Agent orqali javob berish (Function Calling tsikli bilan).
        """
        if not self.api_key:
            return "AI Agent ishlashi uchun `GEMINI_API_KEY` sozlanmagan."

        # Xabarlar kontekstini tuzish
        contents = []

        if chat_history and isinstance(chat_history, list):
            for item in chat_history[-4:]:  # Oxirgi 4 ta xabar tarixi
                role = "user" if item.get("role") == "user" else "model"
                text = item.get("text", "")
                if text:
                    contents.append({
                        "role": role,
                        "parts": [{"text": text}]
                    })

        contents.append({
            "role": "user",
            "parts": [{"text": question}]
        })

        last_error = None

        # Modellarni ketma-ket sinab ko'rish
        for model in self.models_to_try:
            iteration_contents = [dict(c) for c in contents]
            try:
                # 1-qadam: Gemini ga so'rov yuborish (Function Calling tekshirish)
                response_data = self._call_gemini_api(model, iteration_contents, with_tools=True)
                candidates = response_data.get("candidates") or []
                if not candidates:
                    continue

                model_parts = candidates[0].get("content", {}).get("parts", [])
                fn_call = None
                for part in model_parts:
                    if "functionCall" in part:
                        fn_call = part["functionCall"]
                        break

                # Agar model Tool chaqirishni talab qilsa
                if fn_call:
                    fn_name = fn_call.get("name")
                    fn_args = fn_call.get("args") or {}

                    # Tool ni bajarish va natijani olish
                    tool_result = self._execute_tool(fn_name, fn_args)

                    # Model javobini (thoughtSignature bilan birga) to'liq qo'shamiz:
                    iteration_contents.append({
                        "role": "model",
                        "parts": model_parts
                    })
                    # Gemini v1beta da functionResponse "user" roli ostida yuboriladi:
                    iteration_contents.append({
                        "role": "user",
                        "parts": [{
                            "functionResponse": {
                                "name": fn_name,
                                "response": {
                                    "name": fn_name,
                                    "content": tool_result
                                }
                            }
                        }]
                    })

                    # 2-qadam: Funksiya natijasi bilan yakuniy javobni olish
                    final_resp = self._call_gemini_api(model, iteration_contents, with_tools=False)
                    final_candidates = final_resp.get("candidates") or []
                    if final_candidates:
                        final_parts = final_candidates[0].get("content", {}).get("parts", [])
                        final_text = "\n".join(p.get("text", "").strip() for p in final_parts if p.get("text")).strip()
                        if final_text:
                            return self._clean_text(final_text)

                # Agar Tool chaqirilmasdan to'g'ridan-to'g'ri matn qaytgan bo'lsa
                text = "\n".join(p.get("text", "").strip() for p in model_parts if p.get("text")).strip()
                if text:
                    return self._clean_text(text)

            except urlerror.HTTPError as exc:
                last_error = exc
                logger.warning(f"Model {model} failed with code {exc.code}")
                continue
            except Exception as exc:
                last_error = exc
                logger.warning(f"Model {model} error: {exc}")
                continue

        if last_error:
            logger.error(f"Sopline AI Agent barcha modellarda xatolik berdi: {last_error}")
            return "Hozirda AI xizmatiga ulanishda vaqtinchalik uzilish yuz berdi. Iltimos, bir ozdan so'ng qayta urinib ko'ring."

        return "Kechirasiz, savolingizga javob shakllantirib bo'lmadi."
