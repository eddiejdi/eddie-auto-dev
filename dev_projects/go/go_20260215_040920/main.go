package main

import (
	"fmt"
	"net/http"
)

// JiraAPI represents the API to interact with Jira
type JiraAPI struct {
	URL    string
	Token  string
}

// CreateJiraAPI creates a new instance of JiraAPI
func CreateJiraAPI(url, token string) *JiraAPI {
	return &JiraAPI{
		URL: url,
		Token: token,
	}
}

// GetIssue retrieves an issue from Jira
func (j *JiraAPI) GetIssue(issueKey string) (*http.Response, error) {
	req, err := http.NewRequest("GET", j.URL+"/rest/api/2/issue/"+issueKey, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+j.Token)

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}

	return resp, nil
}

// UpdateIssue updates an issue in Jira
func (j *JiraAPI) UpdateIssue(issueKey string, payload map[string]interface{}) (*http.Response, error) {
	req, err := http.NewRequest("PUT", j.URL+"/rest/api/2/issue/"+issueKey, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+j.Token)
	req.Header.Set("Content-Type", "application/json")

	jsonPayload, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	req.Body = io.NopCloser(bytes.NewBuffer(jsonPayload))

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}

	return resp, nil
}

// Main function to demonstrate the usage of JiraAPI
func main() {
	jira := CreateJiraAPI("https://your-jira-instance.atlassian.net", "your-api-token")

	issueKey := "ABC-123"
	resp, err := jira.GetIssue(issueKey)
	if err != nil {
		fmt.Println("Error getting issue:", err)
		return
	}
	defer resp.Body.Close()

	fmt.Println("Response from Jira API:")
	fmt.Println(string(resp.Body.Bytes()))

	payload := map[string]interface{}{
		"fields": map[string]interface{}{
			"description": "Updated description for the issue",
		},
	}

	resp, err = jira.UpdateIssue(issueKey, payload)
	if err != nil {
		fmt.Println("Error updating issue:", err)
		return
	}
	defer resp.Body.Close()

	fmt.Println("Response from Jira API after update:")
	fmt.Println(string(resp.Body.Bytes()))
}