import com.atlassian.jira.JiraService;
import com.atlassian.jira.service.ServiceManager;
import com.atlassian.jira.service.ServiceManagerFactory;
import com.atlassian.jira.user.ApplicationUser;
import com.atlassian.jira.user.UserManager;
import com.atlassian.jira.web.action.issue.IssueAction;
import com.atlassian.jira.web.action.issue.IssueActionSupport;

public class JavaAgentJiraIntegration {

    public static void main(String[] args) {
        // Configuração do JiraService
        ServiceManagerFactory serviceManagerFactory = ServiceManagerFactory.getInstance();
        ServiceManager serviceManager = serviceManagerFactory.getServiceManager();
        JiraService jiraService = serviceManager.getJiraService();

        // Configuração do UserManager
        UserManager userManager = serviceManager.getUserManager();

        // Configuração do ApplicationUser (exemplo)
        ApplicationUser user = userManager.getUserByName("username");

        // Criação de uma nova atividade no Jira
        IssueAction issueAction = new IssueActionSupport();
        issueAction.setIssue(user.getIssue());
        issueAction.setActionName("New Activity");
        issueAction.execute();

        System.out.println("Activity created in Jira.");
    }
}