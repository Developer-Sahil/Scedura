from datetime import datetime
from typing import Optional, List
import json
import os

from google import genai
from google.genai import types

from schemas import MeetingRequest
from calendar_service import create_calendar_event, find_event, delete_event
from database import User

class MeetingAgent:
    def __init__(self, user: User):
        self.user = user
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        # Use gemini-2.0-flash as it is the latest and supports tool calling well
        self.model_id = "gemini-2.0-flash"
        self.chat_history = [] 
        self.last_booked_link = None

    def _get_tools(self):
        """Returns the function definitions for the model."""
        return [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="book_meeting",
                        description="Book a 30-minute meeting on the calendar.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "name": types.Schema(type="STRING", description="The name of the person requesting the meeting."),
                                "date": types.Schema(type="STRING", description="The date of the meeting in YYYY-MM-DD format."),
                                "time": types.Schema(type="STRING", description="The time of the meeting in HH:MM (24h) or H:MM AM/PM format."),
                                "title": types.Schema(type="STRING", description="Optional title for the meeting."),
                            },
                            required=["name", "date", "time"]
                        )
                    ),
                    types.FunctionDeclaration(
                        name="cancel_meeting",
                        description="Cancel/delete a meeting from the calendar.",
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "name": types.Schema(type="STRING", description="The name of the person finding the meeting to cancel."),
                                "date": types.Schema(type="STRING", description="The date of the meeting to cancel in YYYY-MM-DD format."),
                            },
                            required=["name", "date"]
                        )
                    )
                ]
            )
        ]

    async def chat(self, user_input: str, history: List = []) -> tuple[str, Optional[str]]:
        """
        Main entry point for chat using internal history.
        """
        # Load and convert history if provided. 
        # Expecting history to be list of objects like {'role': 'user', 'text': '...'}
        if history:
            self.chat_history = []
            for item in history:
                role = item.get("role")
                text = item.get("text")
                if role and text:
                    self.chat_history.append(types.Content(role=role, parts=[types.Part(text=text)]))

        current_time = datetime.now().strftime("%A, %Y-%m-%d %H:%M")
        
        system_instruction = f"""
            You are a helpful meeting scheduling assistant named 'Scedura'.
            Your primary goal is to help users book or cancel meetings on the *User's personal calendar*.
            
            Current Date and Time: {current_time}
            
            - To BOOK a meeting: Extract (name, date, time, title) and call 'book_meeting'.
            - To CANCEL a meeting: Extract (name, date) and call 'cancel_meeting'.
            
            CRITICAL RULES:
            1. Always REMEMBER information provided in previous messages. If the user already gave you a name or a date, DO NOT ASK FOR IT AGAIN.
            2. If you have enough information to call a tool, call it immediately.
            3. After a tool call, confirm the success to the user (e.g., "I've booked your meeting...").
            
            Keep your responses concise and friendly.
            """

        # Append new user message
        self.chat_history.append(types.Content(role="user", parts=[types.Part(text=user_input)]))

        try:
            # Generate response using async client
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=self.chat_history,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=self._get_tools(),
                )
            )

            # Handle potential tool calls in a loop
            while response.candidates[0].content.parts and response.candidates[0].content.parts[0].function_call:
                self.chat_history.append(response.candidates[0].content)
                
                tool_results_parts = []
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        fc = part.function_call
                        print(f"DEBUG: Executing tool {fc.name} with {fc.args}")
                        result = await self._execute_tool(fc.name, fc.args)
                        tool_results_parts.append(types.Part(
                            function_response=types.FunctionResponse(
                                name=fc.name,
                                response={"result": result}
                            )
                        ))
                
                if not tool_results_parts:
                    break

                # Add results back to history
                self.chat_history.append(types.Content(role="user", parts=tool_results_parts))
                
                # Get next response turn
                response = await self.client.aio.models.generate_content(
                    model=self.model_id,
                    contents=self.chat_history,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        tools=self._get_tools(),
                    )
                )

            self.chat_history.append(response.candidates[0].content)
            
            # Extract final text
            final_text = ""
            for part in response.candidates[0].content.parts:
                if part.text:
                    final_text += part.text
            
            if not final_text:
                final_text = "I've processed your request."
                
            return final_text, self.last_booked_link

        except Exception as e:
            print(f"DEBUG: Agent Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return f"I encountered an error: {str(e)}", None

    async def _execute_tool(self, name: str, args: dict):
        if name == "book_meeting":
            try:
                req = MeetingRequest(
                    name=args["name"],
                    date=args["date"],
                    time=args["time"],
                    title=args.get("title")
                )
                result = await create_calendar_event(self.user, req)
                self.last_booked_link = result.calendar_link
                return json.dumps(result.model_dump(), default=str)
            except Exception as e:
                return f"Error booking meeting: {str(e)}"
        elif name == "cancel_meeting":
            try:
                # find_event normally returns the first matching event ID
                event_id = await find_event(self.user, args["name"], args["date"])
                if not event_id:
                    return f"No meeting found for '{args['name']}' on {args['date']}."
                
                await delete_event(self.user, event_id)
                return f"Successfully canceled meeting with '{args['name']}' on {args['date']}."
            except Exception as e:
                return f"Error canceling meeting: {str(e)}"
        return "Unknown tool called."
