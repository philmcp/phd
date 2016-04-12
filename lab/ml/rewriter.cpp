// Usage:
//
//     LD_LIBRARY_PATH=~/phd/tools/llvm/build/lib ./rewriter <file> --
//
#include <memory>
#include <string>
#include <map>

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Weverything"
#include "clang/AST/AST.h"
#include "clang/AST/ASTConsumer.h"
#include "clang/AST/ASTContext.h"
#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/Driver/Options.h"
#include "clang/Frontend/ASTConsumers.h"
#include "clang/Frontend/CompilerInstance.h"
#include "clang/Frontend/FrontendActions.h"
#include "clang/Rewrite/Core/Rewriter.h"
#include "clang/Tooling/CommonOptionsParser.h"
#include "clang/Tooling/Tooling.h"
#pragma GCC diagnostic pop

namespace rewriter {

static clang::Rewriter rewriter;
static llvm::cl::OptionCategory _tool_category("phd");

static std::map<std::string, std::string> _fns;
static std::string _last_fn = "";

static unsigned int _fn_decl_rewrites_counter = 0;
static unsigned int _fn_call_rewrites_counter = 0;

enum ctype { AZ, az };

std::string get_next_name(const std::string& current) {
  auto c = current;
  char *cc = &c[c.length() - 1];
  ctype type;

  while (true) {
    // determine type
    if (*cc >= 'A' && *cc <= 'Z')
      type = ctype::AZ;
    else
      type = ctype::az;

    ++*cc;

    // If the value has overflowed, reset and move to next char.
    if (*cc == 'Z' + 1 || *cc == 'z' + 1) {
      // reset char
      if (type == ctype::AZ)
        *cc = 'A';
      else
        *cc = 'a';


      // If we're at the last character, insert a new one, otherwise
      // just move to the next character to increment.
      if (cc == &c[0]) {
        if (type == ctype::AZ)
          c.insert(c.begin(), 'A');
        else
          c.insert(c.begin(), 'a');
        break;
      } else {
        --cc;
      }
    } else {
      break;
    }
  }

  return c;
}

std::string get_fn_rewrite(const std::string& name) {
  if (_fns.empty()) {
    // First function
    _fns[name] = "A";
    _last_fn = "A";
    return "A";
  } else if (_fns.find(name) == _fns.end()) {
    // New function
    auto replacement = get_next_name(_last_fn);
    _last_fn = replacement;
    _fns[name] = replacement;
    return replacement;
  } else {
    // Previously visited function
    return (*_fns.find(name)).second;
  }
}


class RewriterVisitor : public clang::RecursiveASTVisitor<RewriterVisitor> {
 private:
  std::unique_ptr<clang::ASTContext> astContext;  // additional AST info

  virtual ~RewriterVisitor() {}

 public:
  explicit RewriterVisitor(clang::CompilerInstance *CI)
      : astContext(&(CI->getASTContext())) {
    rewriter.setSourceMgr(astContext->getSourceManager(),
                          astContext->getLangOpts());
  }

  // Rewrite function definitions:
  virtual bool VisitFunctionDecl(clang::FunctionDecl *func) {
    const auto funcName = func->getNameInfo().getName().getAsString();
    const auto replacement = get_fn_rewrite(funcName);

    rewriter.ReplaceText(
        func->getLocation(),
        static_cast<unsigned int>(funcName.length()),
        replacement);
    ++_fn_decl_rewrites_counter;

    return true;
  }

  virtual bool VisitStmt(clang::Stmt *st) {
    // Rewrite function calls:
    if (clang::CallExpr *call = clang::dyn_cast<clang::CallExpr>(st)) {
      const auto callee = call->getDirectCallee();
      if (callee) {
        const auto funcName = callee->getNameInfo().getName().getAsString();
        if (_fns.find(funcName) != _fns.end()) {
          const auto replacement = (*_fns.find(funcName)).second;

          rewriter.ReplaceText(
              call->getLocStart(),
              static_cast<unsigned int>(funcName.length()),
              replacement);
          ++_fn_call_rewrites_counter;
        } else {
          llvm::errs() << "REFUSING TO REWRITE " << funcName << "\n";
        }
      } else {
        llvm::errs() << "unable to get direct callee\n";
      }
    }

    return true;
  }
};


class RewriterASTConsumer : public clang::ASTConsumer {
 private:
  RewriterVisitor *visitor;

 public:
  // override the constructor in order to pass CI
  explicit RewriterASTConsumer(clang::CompilerInstance *CI)
      : visitor(new RewriterVisitor(CI))
  { }

  // override this to call our RewriterVisitor on the entire source file
  virtual void HandleTranslationUnit(clang::ASTContext &Context) {
    /* we can use ASTContext to get the TranslationUnitDecl, which is
       a single Decl that collectively represents the entire source file */
    visitor->TraverseDecl(Context.getTranslationUnitDecl());
  }
};


class RewriterFrontendAction : public clang::ASTFrontendAction {
 public:
  virtual std::unique_ptr<clang::ASTConsumer> CreateASTConsumer(
      clang::CompilerInstance &CI,
      StringRef file) {
    return llvm::make_unique<RewriterASTConsumer>(&CI);
  }
};


}  // namespace rewriter


int main(int argc, const char **argv) {
  clang::tooling::CommonOptionsParser op(argc, argv, rewriter::_tool_category);
  clang::tooling::ClangTool tool(op.getCompilations(), op.getSourcePathList());

  auto result = tool.run(
      clang::tooling::newFrontendActionFactory<
        rewriter::RewriterFrontendAction>().get());

  const auto& id = rewriter::rewriter.getSourceMgr().getMainFileID();
  rewriter::rewriter.getEditBuffer(id).write(llvm::errs());

  llvm::errs() << "\nRewrote " << rewriter::_fn_decl_rewrites_counter
               << " function declarations\n"
               << "Rewrote " << rewriter::_fn_call_rewrites_counter
               << " function calls\n";

  return result;
}
