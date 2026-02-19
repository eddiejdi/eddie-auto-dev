package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
)

// TestCreateJiraIssue tests the createJiraIssue function with valid inputs
func TestCreateJiraIssue(t *testing.T) {
	jiraURL := "https://your-jira-instance.atlassian.net/rest/api/2/issue"
	username := "your-username"
	password := "your-password"

	// Create a new HTTP client
	client := &http.Client{}

	// Prepare the request body for creating an issue
	body := fmt.Sprintf(`{
		"fields": {
			"project": {"key": "YOUR_PROJECT_KEY"},
			"summary": "Test Issue",
			"description": "This is a test issue created by Go Agent."
		}
	}`)

	// Set the request headers
	req, err := http.NewRequest("POST", jiraURL, strings.NewReader(body))
	if err != nil {
		t.Errorf("Error creating request: %v", err)
		return
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", fmt.Sprintf("Basic %s", base64.StdEncoding.EncodeToString([]byte(fmt.Sprintf("%s:%s", username, password)))))

	// Send the request
	resp, err := client.Do(req)
	if err != nil {
		t.Errorf("Error sending request: %v", err)
		return
	}
	defer resp.Body.Close()

	// Read the response body
	bodyBytes, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		t.Errorf("Error reading response body: %v", err)
		return
	}

	// Parse the JSON response
	var issue JiraIssue
	err = json.Unmarshal(bodyBytes, &issue)
	if err != nil {
		t.Errorf("Error parsing JSON response: %v", err)
		return
	}

	fmt.Printf("Created Issue: %+v\n", issue)

	// Example of updating an existing issue (not implemented in this example)
	// updateJiraIssue(jiraURL, username, password, "ISSUE_KEY", "Updated Summary", "Updated Description")
}