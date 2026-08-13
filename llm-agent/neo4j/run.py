import subprocess
import sys
import os
import time

def run_script(script_name, description):
    """运行指定的Python脚本"""
    print(f"\n{'='*50}")
    print(f"正在运行: {description}")
    print(f"{'='*50}")
    
    try:
        # 使用subprocess运行脚本
        result = subprocess.run([sys.executable, script_name], 
                              capture_output=False, 
                              text=True, 
                              cwd=os.getcwd())
        
        if result.returncode == 0:
            print(f"\n{description} 执行成功！")
            return True
        else:
            print(f"\n{description} 执行失败，返回码: {result.returncode}")
            return False
            
    except Exception as e:
        print(f"\n运行 {script_name} 时发生错误: {str(e)}")
        return False

def check_file_exists(filename):
    """检查文件是否存在"""
    return os.path.exists(filename)

def wait_for_file_update(filename, timeout=30):
    """等待文件更新"""
    print(f"\n等待 {filename} 文件更新...")
    
    start_time = time.time()
    initial_mtime = os.path.getmtime(filename) if os.path.exists(filename) else 0
    
    while time.time() - start_time < timeout:
        if os.path.exists(filename):
            current_mtime = os.path.getmtime(filename)
            if current_mtime > initial_mtime:
                print(f"{filename} 已更新！")
                return True
        time.sleep(1)
    
    print(f"等待 {filename} 更新超时")
    return False

def main():
    # 检查必要文件是否存在
    required_files = ['industry_chain_generator.py', 'neo4j_industry_chain.py']
    for file in required_files:
        if not check_file_exists(file):
            print(f"错误: 找不到必要文件 {file}")
            return False
    
    # 步骤1: 运行产业链数据生成器
    success = run_script('industry_chain_generator.py', '产业链数据生成器')
    if not success:
        print("\n产业链数据生成失败，流程终止")
        return False
    
    # 步骤2: 检查industry_test.json是否生成/更新
    if not check_file_exists('industry_test.json'):
        print("\n错误: industry_test.json 文件未生成")
        return False
    
    print("\nindustry_test.json 文件已生成")
    
    # 给用户一个短暂的确认时间
    print("\n准备创建Neo4j图谱...")
    time.sleep(2)
    
    # 步骤3: 运行Neo4j图谱生成器
    success = run_script('neo4j_industry_chain.py', 'Neo4j图谱生成器')
    if not success:
        print("\nNeo4j图谱生成失败")
        return False
    
    print("\n产业链图谱生成流程完成！")
    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n所有步骤执行成功！")
        else:
            print("\n执行过程中出现错误")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n用户中断执行")
        sys.exit(1)
    except Exception as e:
        print(f"\n发生未预期的错误: {str(e)}")
        sys.exit(1)

# TODO
# 1.输出内容不要用中文  给模型的prompt是全英文
# 2.缺少原料的库存 