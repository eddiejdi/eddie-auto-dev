import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.jira.service.ServiceContext;
import com.atlassian.jira.web.action.JiraActionSupport;

public class JavaAgentJiraIntegration extends JiraActionSupport {

    private static final long serialVersionUID = 1L;

    private IssueManager issueManager;
    private ProjectManager projectManager;

    public JavaAgentJiraIntegration() {
        this.issueManager = ComponentAccessor.getComponent(IssueManager.class);
        this.projectManager = ComponentAccessor.getComponent(ProjectManager.class);
    }

    @Override
    public String doExecute() throws Exception {
        // Simulação de uma atividade no sistema
        Issue issue = createIssue("Task", "Implement Java Agent integration with Jira");
        projectManager.updateProject(issue.getProjectObject(), true);

        return SUCCESS;
    }

    private Issue createIssue(String summary, String description) {
        ServiceContext serviceContext = ComponentAccessor.getOSGiComponentInstanceOfType(ServiceContext.class);
        Project project = projectManager.getProjectByKey("YOUR_PROJECT_KEY"); // Substitua pela chave do projeto em Jira

        Issue issue = issueManager.createIssue(serviceContext, project, summary, description);
        return issue;
    }
}