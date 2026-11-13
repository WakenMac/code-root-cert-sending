from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Defines the specific permissions our bot account needs. "drive.readonly" allows searching and downloading.
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
SERVICE_ACCOUNT_FILE = 'certificate-sending-a333fb30ef79.json'

# Extracts the unique Folder ID from a standard Google Drive folder URL.
# If your link is https://drive.google.com/drive/folders/1aBcDeFgHiJkLmNoP, the ID is "1aBcDeFgHiJkLmNoP".
TARGET_FOLDER_ID = '1-SEL8MnrnzypeyeSXWNaKUP20wa2YDOQ' 

# Loads the JSON key and generates secure cryptographic tokens using the defined scopes.
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

# Builds the official Drive API client, instructing it to use version 'v3' and our generated credentials.
drive_service = build('drive', 'v3', credentials=creds)

app = FastAPI(
    title="Certificate Generation API",
    description="API to generate dynamic custom-font certificates using Pillow and FastAPI.",
    version="1.0",
)

class CertificateRequest(BaseModel):
    tuteeId: str

@app.post("/get-certificate/")
def get_certificate(payload: CertificateRequest):
    
    # We use a try-except block to gracefully handle network errors or missing files without crashing the server.
    try:
        # 1. Connect to Google Drive & Search for the PDF
        # We construct a Google Drive search query. It strictly filters for:
        # - Files located directly inside our target folder
        # - Files whose title contains the exact tutee_id
        # - Files that are specifically PDFs
        # - Files that are not in the trash bin
        query = (
            f"'{TARGET_FOLDER_ID}' in parents and "
            f"name contains '{payload.tutee_id}' and "
            f"mimeType = 'application/pdf' and "
            f"trashed = false"
        )
        
        # Executes the search query. We limit the response to 1 file and ask only for the 'id' and 'name' fields to save bandwidth.
        results = drive_service.files().list(
            q=query, 
            pageSize=1, 
            fields="files(id, name)"
        ).execute()
        
        files = results.get('files', [])
        
        # If the search array is empty, the certificate hasn't been generated or uploaded yet.
        # We immediately halt execution and return an HTTP 404 (Not Found) error to the client.
        if not files:
            raise HTTPException(status_code=404, detail=f"Certificate not found for tutee ID: {payload.tutee_id}")
            
        file_id = files[0]['id']
        file_name = files[0]['name']
        
        # 2. Get the Google Drive file as a Blob (Raw Bytes)
        # We request the raw media content of the file using its internal Google Drive ID.
        # .execute() performs the HTTP GET request and stores the raw binary data in memory.
        file_content = drive_service.files().get_media(fileId=file_id).execute()
        
        # 3. Return the PDF as a Blob
        # We package the raw binary data into a FastAPI Response object.
        # Setting the media_type to "application/pdf" explicitly tells the receiving browser or client 
        # how to interpret the blob (allowing them to render or download it correctly).
        # We inject a "Content-Disposition" header to suggest the original filename if the user saves it.
        return Response(
            content=file_content, 
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{file_name}"'}
        )

    # Catches specific errors returned by the Google API (like authentication failures or missing permissions)
    except HttpError as error:
        raise HTTPException(status_code=500, detail=f"Google Drive API error: {error}")