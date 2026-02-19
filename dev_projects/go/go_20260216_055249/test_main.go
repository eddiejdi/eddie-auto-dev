package main

import (
	"testing"
)

// TestNewJiraClient verifica se NewJiraClient é criado corretamente
func TestNewJiraClient(t *testing.T) {
	jiraClient := NewJiraClient("https://your-jira-instance.atlassian.net", "your-api-token")
	if jiraClient == nil {
		t.Errorf("NewJiraClient should not return nil")
	}
}

// TestGetIssue verifica se GetIssue retorna uma resposta HTTP correta
func TestGetIssue(t *testing.T) {
	jiraClient := NewJiraClient("https://your-jira-instance.atlassian.net", "your-api-token")

	req, err := http.NewRequest("GET", jiraClient.url+"/rest/api/2/issue/ABC-123", nil)
	if err != nil {
		t.Errorf("NewJiraClient should not return nil")
	}

	resp, err := jiraClient.client.Do(req)
	if err != nil {
		t.Errorf("GetIssue should not return nil")
	}
	defer resp.Body.Close()

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		t.Errorf("GetIssue should not return nil")
	}

	fmt.Println(string(body))
}

// TestUpdateIssue verifica se UpdateIssue retorna uma resposta HTTP correta
func TestUpdateIssue(t *testing.T) {
	jiraClient := NewJiraClient("https://your-jira-instance.atlassian.net", "your-api-token")

	updatePayload := `{
		"fields": {
			"description": "Updated issue description",
			"status": {
				"name": "In Progress"
			}
		}
	}`

	resp, err := jiraClient.UpdateIssue("ABC-123", updatePayload)
	if err != nil {
		t.Errorf("UpdateIssue should not return nil")
	}
	defer resp.Body.Close()

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		t.Errorf("UpdateIssue should not return nil")
	}

	fmt.Println(string(body))
}