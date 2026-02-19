package main

import (
	"fmt"
	"github.com/jenkinsci/go-agent/api"
	"github.com/jenkinsci/go-agent/config"
	"github.com/jenkinsci/go-agent/server"
)

func main() {
	// Configuração do Go Agent
	config := config.NewConfig()
	config.JiraURL = "https://your-jira-instance.atlassian.net/rest/api/2.0/"
	config.Username = "your-username"
	config.Password = "your-password"

	// Cria o servidor do Go Agent
	server := server.NewServer(config)

	// Inicia o servidor
	if err := server.Start(); err != nil {
		fmt.Println("Error starting the Go Agent:", err)
		return
	}

	fmt.Println("Go Agent started successfully")
}