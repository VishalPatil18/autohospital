from __future__ import annotations

from typing import AsyncIterator

from anthropic import AsyncAnthropic

from app.core.config import settings


class AnthropicClient:
    def __init__(self) -> None:
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-6"

    async def chat(
        self,
        messages: list[dict],
        context_chunks: list[str],
        scope: str,
    ) -> AsyncIterator[str]:
        """
        Stream chat responses token by token.

        Args:
            messages: Conversation history as list of {"role": ..., "content": ...} dicts.
            context_chunks: Retrieved document chunks to inject as context.
            scope: Either "patient" or "doctor" — adjusts system prompt tone.

        Yields:
            Individual text tokens from the model.
        """
        if scope == "doctor":
            tone = (
                "You are a clinical decision-support AI assisting a licensed physician. "
                "Use precise medical terminology. Cite evidence where relevant."
            )
        else:
            tone = (
                "You are a friendly medical assistant helping a patient understand their health. "
                "Use plain, accessible language. Never diagnose; always recommend consulting a doctor."
            )

        context_section = ""
        if context_chunks:
            joined = "\n\n---\n\n".join(context_chunks)
            context_section = f"\n\n<context>\n{joined}\n</context>"

        system_content = f"{tone}{context_section}"

        # Use prompt caching on the system prompt to reduce repeated token cost
        system_block = [
            {
                "type": "text",
                "text": system_content,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=2048,
            system=system_block,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def summarize_consultation(self, transcript: str) -> tuple[str, str]:
        """
        Summarize a consultation transcript into a SOAP note and a patient-friendly note.

        Returns:
            (soap_note, patient_friendly_note)
        """
        soap_prompt = (
            "You are a clinical documentation specialist. "
            "Given the following consultation transcript, produce a structured SOAP note "
            "(Subjective, Objective, Assessment, Plan). Be thorough and use medical terminology.\n\n"
            f"<transcript>\n{transcript}\n</transcript>\n\n"
            "Respond with only the SOAP note text."
        )

        soap_response = await self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=[
                {
                    "type": "text",
                    "text": "You are a clinical documentation specialist.",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": soap_prompt}],
        )
        soap_text = soap_response.content[0].text

        patient_prompt = (
            "You are a patient advocate. Rewrite the following clinical SOAP note into a "
            "friendly, easy-to-understand summary for a patient with no medical background. "
            "Avoid jargon; use simple English. Include what the doctor found, the diagnosis, "
            "and what the patient should do next.\n\n"
            f"<soap_note>\n{soap_text}\n</soap_note>\n\n"
            "Respond with only the patient-friendly summary."
        )

        patient_response = await self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": patient_prompt}],
        )
        patient_text = patient_response.content[0].text

        return soap_text, patient_text

    async def translate_document(self, text: str) -> str:
        """
        Translate a medical document into plain English with a glossary of terms.

        Returns:
            Plain-English version of the document with a glossary appended.
        """
        prompt = (
            "You are a medical translator specializing in making clinical documents accessible "
            "to patients. Translate the following medical document into plain English that a "
            "patient with a 10th-grade reading level can understand.\n\n"
            "After the plain-English translation, append a 'Medical Glossary' section that "
            "defines any medical or technical terms you encountered, in alphabetical order.\n\n"
            f"<document>\n{text}\n</document>\n\n"
            "Format your response as:\n"
            "## Plain English Summary\n<your translation>\n\n"
            "## Medical Glossary\n<term>: <definition>\n..."
        )

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=[
                {
                    "type": "text",
                    "text": "You are a medical translator making clinical documents accessible to patients.",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
