package main_test

import (
	"testing"

	"github.com/jenkinsci/go-agent/api"
	"github.com/jenkinsci/go-agent/config"
	"github.com/jenkinsci/go-agent/server"
)

func TestMain(t *testing.T) {
	config := config.NewConfig()
	config.JiraURL = "https://your-jira-instance.atlassian.net/rest/api/2.0/"
	config.Username = "your-username"
	config.Password = "your-password"

	server := server.NewServer(config)
	if err := server.Start(); err != nil {
		t.Errorf("Error starting the Go Agent: %v", err)
		return
	}

	fmt.Println("Go Agent started successfully")
}