import asyncio
import requests
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


def get_valid_token():
    """
    Example function to get a valid token via the /auth/exchange endpoint.
    In practice, you would first complete the OAuth flow to get an auth_code.
    """
    # This is a placeholder - in real usage, you would:
    # 1. Direct user to /auth/login
    # 2. User completes OAuth flow and gets auth_code
    # 3. Exchange auth_code for token using this function
    
    auth_code = input("Enter the auth_code from the login flow: ")
    
    response = requests.post(
        "http://localhost:8000/auth/exchange",
        json={"auth_code": auth_code}
    )
    
    if response.status_code == 200:
        token_data = response.json()
        return token_data.get("access_token")
    else:
        raise Exception(f"Failed to get token: {response.text}")


async def test():
    try:
        # Get a valid bearer token via /auth/exchange
        token = get_valid_token()
        
        client = Client(StreamableHttpTransport(
            "http://localhost:8000/weather-mcp/mcp/",
            auth=token
        ))
        
        async with client:
            result = await client.list_tools()
            if not result:
                print("No tools available for this user.")
            else:
                print("Available tools:")
                for tool in result:
                    print(f"- {tool.name}")
    except Exception as e:
        print(f"Failed to list tools: {e}")


if __name__ == "__main__":
    asyncio.run(test())

# Example Output:
# Available tools:
# - get_weather
# - get_forecast